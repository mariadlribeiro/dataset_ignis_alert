#!/usr/bin/env python3
"""
Etapa 10d - INTEGRAÇÃO da seleção revisada da nova fonte ao dataset organizado.

Plano aprovado em 12/11/2026 (opção A): igualar a floresta (510 com fogo x 510 sem fogo, em cada conjunto) e
incluir as demais imagens revisadas (campo, cidade, prédios, casa sem fogo). Regras mantidas:
  * os originais (pasta do kagglehub) só são LIDOS; a cópia é byte a byte e conferida por SHA-256;
  * nenhuma imagem que já estava no dataset muda de conjunto (treino/validação/teste congelados);
  * imagens da mesma cena ou vídeo (cenas.csv) e quase duplicatas (dHash <= --limiar) ficam no MESMO conjunto;
  * nada é excluído: o que não entra vai para fora.csv com o motivo;
  * a origem de cada rótulo fica registrada (revisao_ia ou decisao_humana); a pasta da fonte não é rótulo.

Entradas em relatorios/10_nova_fonte/<nome>/:
  arquivos.csv (10a), selecao_A/sugestoes.csv (10c), selecao_A/revisao_floresta_A_ia.csv (revisão),
  selecao_A/decisoes.csv (decisões que mudam ou excluem uma linha), selecao_A/cenas.csv (cenas repetidas)
  e relatorios/06_plano/inventario.csv (dataset atual).
Saídas em relatorios/10_nova_fonte/<nome>/integracao_A/:
  inventario_novas.csv -> as imagens que entram, nas mesmas colunas do inventário
  fora.csv             -> as revisadas que não entram, com motivo
  log_copia.csv        -> o que foi copiado e a conferência do SHA (só com --executar)
  resumo.txt
e relatorios/10_nova_fonte/inventario_combinado.csv (atual + novas), que a Etapa 8 passa a usar.

Uso:  python scripts/10d_integrar_fonte.py --nova "C:\\...\\versions\\2"              (simula; não copia)
      python scripts/10d_integrar_fonte.py --nova "C:\\...\\versions\\2" --executar   (copia e confere)
"""
import argparse, csv, hashlib, random, re, shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

SPLITS = ("treino", "validacao", "teste")
EXT = {"JPEG": ".jpg", "MPO": ".jpg", "PNG": ".png", "GIF": ".gif", "BMP": ".bmp", "WEBP": ".webp", "TIFF": ".tif"}

# Decisões de 12/11/2026 sobre a seleção A. Só são gravadas em selecao_A/ se os arquivos ainda não existirem;
# depois disso valem os CSVs (edite os CSVs, não este bloco).
DECISOES_PADRAO = [  # n, decisao, ambiente, fogo, fumaca, motivo, quem
    ('113', 'fora', '', '', '', 'excedente da meta 510 x 510: quadro repetido da mata nevada (nº 103 e 107 entram)', 'revisao_ia'),
    ('117', 'fora', '', '', '', 'excedente da meta 510 x 510: quadro repetido da mata nevada (nº 103 e 107 entram)', 'revisao_ia'),
    ('120', 'fora', '', '', '', 'excedente da meta 510 x 510: quadro repetido da mata nevada (nº 103 e 107 entram)', 'revisao_ia'),
    ('126', 'fora', '', '', '', 'excedente da meta 510 x 510: quadro repetido da mata nevada (nº 103 e 107 entram)', 'revisao_ia'),
    ('130', 'fora', '', '', '', 'excedente da meta 510 x 510: quadro repetido da mata nevada (nº 103 e 107 entram)', 'revisao_ia'),
    ('307', 'fora', '', '', '', 'tela só com texto, sem cena', 'revisao_ia'),
    ('314', 'incluir', 'outros', 'sim', 'sim', 'linha de chamas visível no horizonte à noite (conferida em tamanho maior)', 'revisao_ia'),
    ('319', 'fora', '', '', '', 'imagem muito editada (cores e céu artificiais)', 'decisao_humana'),
    ('325', 'fora', '', '', '', 'fogo controlado (lareira acesa e velas)', 'decisao_humana'),
    ('337', 'fora', '', '', '', 'excedente da meta 510 x 510: mesma cena da nº 223, que entra', 'revisao_ia'),
    ('342', 'fora', '', '', '', 'montagem (carro com rodas duplicadas)', 'revisao_ia'),
    ('353', 'incluir', 'cidade', 'nao', 'sim', 'coluna de fumaça saindo de prédio, sem chama visível (conferida em tamanho maior)', 'revisao_ia'),
]
CENAS_PADRAO = [  # n, cena (imagens da mesma cena ou vídeo ficam no mesmo conjunto)
    ('163', 'riacho_na_mata'),
    ('164', 'riacho_na_mata'),
    ('165', 'riacho_na_mata'),
    ('103', 'mata_nevada_aerea'),
    ('107', 'mata_nevada_aerea'),
    ('167', 'mata_nevada_aerea'),
    ('168', 'mata_nevada_aerea'),
    ('174', 'mata_nevada_aerea'),
    ('177', 'mata_nevada_aerea'),
    ('170', 'margem_de_rio'),
    ('171', 'margem_de_rio'),
    ('172', 'margem_de_rio'),
    ('175', 'mata_tropical_aerea'),
    ('176', 'mata_tropical_aerea'),
    ('153', 'mata_aerea'),
    ('154', 'mata_aerea'),
    ('155', 'mata_aerea'),
    ('299', 'pedreira_aerea'),
    ('300', 'pedreira_aerea'),
    ('380', 'encosta_com_neblina'),
    ('381', 'encosta_com_neblina'),
    ('252', 'riacho_de_outono'),
    ('253', 'riacho_de_outono'),
    ('254', 'riacho_de_outono'),
    ('255', 'riacho_de_outono'),
    ('322', 'fogos_de_artificio'),
    ('328', 'fogos_de_artificio'),
    ('333', 'fogos_de_artificio'),
    ('341', 'fogos_de_artificio'),
    ('349', 'fogos_de_artificio'),
    ('352', 'fogos_de_artificio'),
    ('355', 'fogos_de_artificio'),
]


def ler(caminho):
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def gravar(caminho, linhas, cols):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(linhas)


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def origem(nova, rel):
    return nova / Path(*rel.replace("\\", "/").split("/"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nova", required=True)
    ap.add_argument("--nome", default="cristiancristancho_forest-fire-image-dataset")
    ap.add_argument("--dataset-ref", default="cristiancristancho/forest-fire-image-dataset")
    ap.add_argument("--versao", default="2")
    ap.add_argument("--prefixo", default="forest-fire-image-dataset")
    ap.add_argument("--inventario", default="relatorios/06_plano/inventario.csv")
    ap.add_argument("--destino", default="data/dataset_organizado")
    ap.add_argument("--saida", default="relatorios/10_nova_fonte")
    ap.add_argument("--limiar", type=int, default=10, help="dHash até este valor junta duas imagens novas na mesma unidade")
    ap.add_argument("--semente", type=int, default=42)
    ap.add_argument("--executar", action="store_true", help="sem isto, só simula")
    a = ap.parse_args()

    nova, pasta = Path(a.nova), Path(a.saida) / a.nome
    sel, sai = pasta / "selecao_A", pasta / "integracao_A"
    sai.mkdir(parents=True, exist_ok=True)
    arq = {r["caminho_relativo"]: r for r in ler(pasta / "arquivos.csv")}
    sug = {r["caminho_relativo"]: r for r in ler(sel / "sugestoes.csv")}
    rev = ler(sel / "revisao_floresta_A_ia.csv")
    if not (sel / "decisoes.csv").exists():
        gravar(sel / "decisoes.csv", [dict(zip(["n", "decisao", "ambiente", "fogo", "fumaca", "motivo", "quem"], d)) for d in DECISOES_PADRAO],
               ["n", "decisao", "ambiente", "fogo", "fumaca", "motivo", "quem"])
    if not (sel / "cenas.csv").exists():
        gravar(sel / "cenas.csv", [dict(zip(["n", "cena"], c)) for c in CENAS_PADRAO], ["n", "cena"])
    dec = {int(r["n"]): r for r in ler(sel / "decisoes.csv")}
    cena = {int(r["n"]): r["cena"] for r in ler(sel / "cenas.csv")}
    atual = ler(a.inventario)
    cols = list(atual[0].keys())

    # 1) rótulo final de cada imagem revisada
    entram, fora = [], []
    for r in rev:
        n, cam = int(r["n"]), r["caminho_relativo"]
        d = dec.get(n)
        amb, fogo, fum, fonte = r["ambiente_ia"], r["fogo_ia"], r["fumaca_ia"], "revisao_ia"
        if d and d["decisao"] == "fora":
            fora.append({"n": n, "caminho_relativo": cam, "motivo": d["motivo"], "quem_decidiu": d["quem"]}); continue
        if d:
            amb, fogo, fum, fonte = d["ambiente"] or amb, d["fogo"] or fogo, d["fumaca"] or fum, d["quem"]
        if fogo not in ("sim", "nao"):
            raise SystemExit(f"nº {n}: fogo '{fogo}' ainda sem decisão (precisa ser sim, nao ou ir para fora em decisoes.csv)")
        entram.append({"n": n, "cam": cam, "amb": amb, "fogo": fogo, "fum": fum, "fonte": fonte, "obs": r["observacao_ia"], "duvida": r["duvida"]})

    # 2) unidades de divisão: cenas anotadas + quase duplicatas entre as novas
    pai = {e["n"]: e["n"] for e in entram}
    def f(x):
        while pai[x] != x: pai[x] = pai[pai[x]]; x = pai[x]
        return x
    por_cena = defaultdict(list)
    for e in entram:
        if e["n"] in cena: por_cena[cena[e["n"]]].append(e["n"])
    for ns in por_cena.values():
        for n in ns[1:]: pai[f(n)] = f(ns[0])
    hs = [(e["n"], int(arq[e["cam"]]["dhash"], 16)) for e in entram]
    for i in range(len(hs)):
        for j in range(i + 1, len(hs)):
            if bin(hs[i][1] ^ hs[j][1]).count("1") <= a.limiar:
                pai[f(hs[j][0])] = f(hs[i][0])
    unidades = defaultdict(list)
    for e in entram: unidades[f(e["n"])].append(e)

    # 3) cotas por estrato (ambiente|fogo). Floresta: completa o que falta para igualar com fogo x sem fogo.
    cont_atual = Counter((r["split"], r["ambiente"], r["fogo"]) for r in atual if r["situacao"] == "incluida")
    n_estrato = Counter((e["amb"], e["fogo"]) for e in entram)
    cota = {}
    for (amb, fogo), n in n_estrato.items():
        outro = "sim" if fogo == "nao" else "nao"
        falta = {s: cont_atual[(s, amb, outro)] - cont_atual[(s, amb, fogo)] for s in SPLITS}
        if amb == "floresta" and all(v >= 0 for v in falta.values()) and sum(falta.values()) == n:
            cota[(amb, fogo)] = dict(falta)                       # iguala exatamente em cada conjunto
        else:
            v = max(1, round(0.15 * n)) if n >= 3 else 0
            cota[(amb, fogo)] = {"treino": n - 2 * v, "validacao": v, "teste": v}
    posto = {k: Counter() for k in cota}
    rnd = random.Random(a.semente)
    ordem = sorted(unidades, key=lambda u: min(e["n"] for e in unidades[u])); rnd.shuffle(ordem)
    ordem.sort(key=lambda u: -len(unidades[u]))                    # unidades grandes primeiro
    split_de = {}
    for u in ordem:
        membros = unidades[u]
        def resto(s): return [cota[(e["amb"], e["fogo"])][s] - posto[(e["amb"], e["fogo"])][s] for e in membros]
        s = max(SPLITS, key=lambda s: (min(resto(s)) >= 1, sum(resto(s)), -SPLITS.index(s)))
        for e in membros:
            posto[(e["amb"], e["fogo"])][s] += 1; split_de[e["n"]] = s

    # 4) linhas de inventário
    nomes = Counter(); novas = []
    usados = {r["nome_novo"].lower() for r in atual}
    num_u = {u: i for i, u in enumerate(sorted(unidades), 1)}
    for e in sorted(entram, key=lambda e: e["n"]):
        x, s = arq[e["cam"]], sug[e["cam"]]
        stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(e["cam"].replace("\\", "/")).stem).strip("_")
        pasta_fonte = Path(e["cam"].replace("\\", "/")).parent.name
        if not stem.upper().startswith(("FIRE", "NON_FIRE")): stem = f"{pasta_fonte}_{stem}"
        nome = f"{a.prefixo}__{stem}{EXT.get(x['formato_real'], x['extensao'])}"
        if nome.lower() in usados: nome = f"{a.prefixo}__{stem}_n{e['n']}{EXT.get(x['formato_real'], x['extensao'])}"
        usados.add(nome.lower()); nomes[nome] += 1
        u = f(e["n"])
        pasta_fogo = "NON_FIRE" not in pasta_fonte.upper()
        novas.append({
            "dataset": a.dataset_ref, "versao": a.versao, "caminho_original": e["cam"],
            "classe_original": str(Path(e["cam"].replace("\\", "/")).parent).replace("\\", "/"),
            "sha256": x["sha256"], "tamanho_bytes": x["bytes"], "formato_real": x["formato_real"], "extensao_original": x["extensao"],
            "largura": x["largura"], "altura": x["altura"], "ambiente": e["amb"], "fonte_ambiente": e["fonte"],
            "fogo": e["fogo"], "fonte_fogo": e["fonte"], "fumaca": e["fum"], "fonte_fumaca": e["fonte"],
            "tipo_imagem": "fotografia", "fonte_tipo": e["fonte"], "camera": "", "camera_sugerida_fraca": s.get("camera_sugerida_fraca", ""),
            "situacao_revisao": "revisada_por_ia", "pasta_diverge_do_fogo": "sim" if pasta_fogo != (e["fogo"] == "sim") else "nao",
            "id_grupo": f"F2G{e['n']:04d}", "unidade_divisao": f"F2U{num_u[u]:04d}", "split": split_de[e["n"]],
            "situacao": "incluida", "motivo": "", "justificativa": "nova fonte, selecao A (12/11/2026)",
            "observacao": "; ".join(t for t in (e["obs"], f"duvida da revisao: {e['duvida']}" if e["duvida"] else "") if t),
            "nome_novo": nome, "destino": f"{a.destino}/{e['amb']}/{'com_fogo' if e['fogo'] == 'sim' else 'sem_fogo'}/{nome}"})
    assert max(nomes.values()) == 1, "nome repetido"
    # verificações
    erros = []
    spl_u = defaultdict(set)
    for r in novas: spl_u[r["unidade_divisao"]].add(r["split"])
    erros += [f"unidade {u} em mais de um conjunto" for u, v in spl_u.items() if len(v) > 1]
    sha_atual = {r["sha256"] for r in atual}
    erros += [f"{r['caminho_original']} já existe no dataset atual (SHA)" for r in novas if r["sha256"] in sha_atual]
    if erros: raise SystemExit("Plano inconsistente:\n  " + "\n  ".join(erros[:20]))

    gravar(sai / "inventario_novas.csv", novas, cols)
    gravar(sai / "fora.csv", fora, ["n", "caminho_relativo", "motivo", "quem_decidiu"])
    combinado = atual + novas
    gravar(Path(a.saida) / "inventario_combinado.csv", combinado, cols)

    # 5) cópia
    log, copiadas, ja = [], 0, 0
    if a.executar:
        for r in novas:
            src, dst = origem(nova, r["caminho_original"]), Path(r["destino"])
            if sha256(src) != r["sha256"]: raise SystemExit(f"ORIGINAL MUDOU desde o inventário: {src}")
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                if sha256(dst) != r["sha256"]: raise SystemExit(f"Já existe um arquivo DIFERENTE em {dst}; nada foi sobrescrito.")
                ja += 1; acao = "ja_existia_identico"
            else:
                shutil.copyfile(src, dst); copiadas += 1; acao = "copiado"
            ok = sha256(dst) == r["sha256"]
            log.append({"caminho_original": r["caminho_original"], "destino": r["destino"], "sha256": r["sha256"], "acao": acao, "sha_confere": "sim" if ok else "NAO"})
            if not ok: raise SystemExit(f"SHA não confere depois da cópia: {dst}")
        gravar(sai / "log_copia.csv", log, list(log[0].keys()))
        inv_dest = Path(a.destino) / "inventario.csv"
        antes = Path(a.destino) / "inventario_so_fonte1.csv"
        if inv_dest.exists() and not antes.exists(): shutil.copyfile(inv_dest, antes)
        gravar(inv_dest, combinado, cols)

    inc = [r for r in combinado if r["situacao"] == "incluida"]
    c = Counter((r["split"], r["ambiente"], r["fogo"]) for r in inc)
    ambs = ["floresta", "predios", "cidade", "casa", "outros"]
    txt = [f"Etapa 10d gerada em {datetime.now(timezone.utc).isoformat(timespec='seconds')} | "
           + ("CÓPIA EXECUTADA e conferida por SHA-256" if a.executar else "SIMULAÇÃO: nada foi copiado"),
           f"fonte: {a.dataset_ref} v{a.versao} | LICENÇA: A CONFERIR na página do Kaggle antes de publicar ou redistribuir",
           f"revisadas: {len(rev)} | entram: {len(novas)} | ficam de fora: {len(fora)} (fora.csv)",
           f"unidades de divisão novas: {len(unidades)} (das quais {sum(1 for u in unidades.values() if len(u) > 1)} com 2+ imagens da mesma cena)",
           f"origem dos rótulos das novas: {dict(Counter(r['fonte_fogo'] for r in novas))}", ""]
    if a.executar: txt += [f"copiadas agora: {copiadas} | já existiam idênticas: {ja} | SHA conferido em {len(log)} de {len(novas)}", ""]
    txt += ["Dataset combinado (com fogo / sem fogo):", f"  {'ambiente':10s} " + " ".join(f"{s:>13s}" for s in SPLITS) + f" {'total':>13s}"]
    for amb in ambs:
        cel = [(c[(s, amb, 'sim')], c[(s, amb, 'nao')]) for s in SPLITS]
        tot = (sum(x[0] for x in cel), sum(x[1] for x in cel))
        txt.append(f"  {amb:10s} " + " ".join(f"{x[0]:6d}/{x[1]:<6d}" for x in cel) + f" {tot[0]:6d}/{tot[1]:<6d}")
    tf = Counter(r["fogo"] for r in inc)
    txt += [f"  TOTAL incluídas: {len(inc)} | com fogo {tf['sim']} | sem fogo {tf['nao']}", "",
            "Entram, por ambiente|fogo e conjunto:"]
    cn = Counter((r["ambiente"], r["fogo"], r["split"]) for r in novas)
    for (amb, fogo), n in sorted(n_estrato.items()):
        txt.append(f"  {amb + '|' + fogo:16s} {n:4d}  treino {cn[(amb, fogo, 'treino')]:3d} | validação {cn[(amb, fogo, 'validacao')]:3d} | teste {cn[(amb, fogo, 'teste')]:3d}")
    txt += ["", f"Arquivos em {sai} e {Path(a.saida) / 'inventario_combinado.csv'}."]
    (sai / "resumo.txt").write_text("\n".join(txt) + "\n", encoding="utf-8")
    print("\n".join(txt))


if __name__ == "__main__":
    main()
