#!/usr/bin/env python3
"""
Etapa 4 - Divisão treino/validação/teste POR GRUPO, sem vazamento (SOMENTE LEITURA).

Regras:
  * a unidade de divisão é o id_grupo (Etapa 3): cópias e quase duplicatas ficam no mesmo conjunto;
  * estratificada pelos rótulos CONSOLIDADOS (Etapa 5d: fogo x ambiente), se rotulos.csv existir;
    sem ele, pela classe original (pasta). A proporção de cada estrato é mantida em cada conjunto;
  * semente fixa -> resultado reproduzível;
  * pares conferidos à mão (pares_revisados.csv, da página 04b): "mesma_cena" une os dois grupos numa
    mesma unidade de divisão (ficam no mesmo split); "cenas_diferentes" registra falso positivo do hash;
  * ficam FORA da divisão (em pendentes.csv, nada é excluído): grupos com conflito de rótulo
    e GIFs animados. Para liberar um caso depois da revisão manual, use --decisoes.

Entradas : relatorios/03_duplicatas/imagem_grupo.csv, conflitos_rotulo.csv, 02_validacao/validacao.csv,
           05_consolidacao/rotulos.csv (opcional, recomendado)
Saídas   : relatorios/04_divisao/
  divisao.csv                      -> caminho_relativo, classe_original, id_grupo, estrato, fogo, ambiente, split
  pendentes.csv                    -> o que ficou fora e por quê
  resumo_divisao.csv               -> contagens e proporções por split x estrato
  pares_proximos_entre_splits.csv  -> pares parecidos (Hamming <= --aviso) em splits diferentes, com o veredito
  pares_candidatos.csv             -> TODOS os pares parecidos entre grupos diferentes (mesmo split ou não):
                                      é a lista que a página 04b mostra, para que nenhuma redivisão crie par novo
  verificacao.txt                  -> resultado das verificações de vazamento

Decisões manuais (opcional), CSV com colunas: caminho_relativo,decisao  (incluir | excluir)
  incluir -> a imagem volta para a divisão com o seu rótulo; excluir -> fica de fora (documentado).

Uso:  python scripts/04_divisao.py [--estrato fogo_ambiente|fogo|classe_original] [--semente 42]
"""
import argparse, csv, json, random
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image

SPLITS = ("treino", "validacao", "teste")


def ler(caminho):
    with open(caminho, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def gravar(caminho, linhas, cols):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(linhas)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--origem", default="relatorios/01_origem/origem.json")
    ap.add_argument("--grupos", default="relatorios/03_duplicatas/imagem_grupo.csv")
    ap.add_argument("--conflitos", default="relatorios/03_duplicatas/conflitos_rotulo.csv")
    ap.add_argument("--validacao", default="relatorios/02_validacao/validacao.csv")
    ap.add_argument("--decisoes", default="relatorios/04_divisao/decisoes_revisao.csv")
    ap.add_argument("--rotulos", default="relatorios/05_consolidacao/rotulos.csv")
    ap.add_argument("--pares-revisados", default="relatorios/04_divisao/pares_revisados.csv")
    ap.add_argument("--estrato", choices=["fogo_ambiente", "fogo", "classe_original"],
                    help="padrão: fogo_ambiente se rotulos.csv existir; senão classe_original")
    ap.add_argument("--saida", default="relatorios/04_divisao")
    ap.add_argument("--treino", type=float, default=0.70)
    ap.add_argument("--val", type=float, default=0.15)
    ap.add_argument("--teste", type=float, default=0.15)
    ap.add_argument("--semente", type=int, default=42)
    ap.add_argument("--aviso", type=int, default=8, help="Hamming p/ listar pares próximos entre splits")
    a = ap.parse_args()
    if abs(a.treino + a.val + a.teste - 1) > 1e-6:
        raise SystemExit("As proporções precisam somar 1.")
    prop = dict(zip(SPLITS, (a.treino, a.val, a.teste)))

    raiz = Path(json.loads(Path(a.origem).read_text(encoding="utf-8"))["caminho_local"])
    saida = Path(a.saida); saida.mkdir(parents=True, exist_ok=True)
    imagens = ler(a.grupos)
    val = {r["caminho_relativo"]: r for r in ler(a.validacao)}
    conflito = {r["caminho_relativo"] for r in ler(a.conflitos)} if Path(a.conflitos).exists() else set()
    decisoes = {r["caminho_relativo"]: r["decisao"].strip().lower()
                for r in ler(a.decisoes)} if Path(a.decisoes).exists() else {}
    rot = {r["caminho_relativo"]: r for r in ler(a.rotulos)} if Path(a.rotulos).exists() else {}
    a.estrato = a.estrato or ("fogo_ambiente" if rot else "classe_original")
    if a.estrato != "classe_original":
        if not rot:
            raise SystemExit(f"--estrato {a.estrato} precisa de {a.rotulos} (rode antes o 05d_consolidar.py)")
        faltam = [r["caminho_relativo"] for r in imagens if r["caminho_relativo"] not in rot]
        if faltam:
            raise SystemExit(f"{len(faltam)} imagens sem rótulo consolidado (ex.: {faltam[0]})")

    def estrato_de(rel, classe):
        if a.estrato == "classe_original":
            return classe
        x = rot[rel]
        return x["fogo"] if a.estrato == "fogo" else f"{x['fogo']}|{x['ambiente']}"

    # --- pendentes ---
    pendentes, incluidas = [], []
    for r in imagens:
        rel, motivo = r["caminho_relativo"], ""
        if rel in conflito:
            motivo = "grupo com conflito de rotulo (classes originais diferentes)"
        elif val.get(rel, {}).get("formato_real") == "GIF":
            with Image.open(raiz / rel) as im:
                if getattr(im, "n_frames", 1) > 1:
                    motivo = f"GIF animado ({im.n_frames} quadros)"
        dec = decisoes.get(rel, "")
        if motivo and dec != "incluir":
            pendentes.append({"caminho_relativo": rel, "classe_original": r["classe_original"],
                              "id_grupo": r["id_grupo"], "motivo": motivo,
                              "decisao": dec or "pendente"})
        elif dec == "excluir":
            pendentes.append({"caminho_relativo": rel, "classe_original": r["classe_original"],
                              "id_grupo": r["id_grupo"], "motivo": "excluida por decisao manual",
                              "decisao": "excluir"})
        else:
            incluidas.append(r)

    # --- unidades de divisão: id_grupo, unindo os grupos de pares marcados como "mesma_cena" ---
    veredito, conflitantes = {}, []
    if Path(a.pares_revisados).exists():
        for p in ler(a.pares_revisados):
            v = p.get("veredito", "").strip().lower()
            if v:
                k = frozenset((p["imagem_a"], p["imagem_b"]))           # a ordem do par não importa
                if k in veredito and veredito[k] != v:
                    conflitantes.append(" x ".join(sorted(k)))
                veredito[k] = v
    if conflitantes:
        raise SystemExit("Vereditos conflitantes para o mesmo par em pares_revisados.csv (corrija na página 04b):\n  "
                         + "\n  ".join(conflitantes))
    grupo_de = {r["caminho_relativo"]: r["id_grupo"] for r in imagens}
    pai = {g: g for g in set(grupo_de.values())}
    def raiz_de(g):
        while pai[g] != g:
            pai[g] = pai[pai[g]]; g = pai[g]
        return g
    unidos = 0
    for par, v in veredito.items():
        if v == "mesma_cena" and len(par) == 2:
            x, y = (raiz_de(grupo_de[c]) for c in par)
            if x != y:
                pai[max(x, y)] = min(x, y); unidos += 1
    unidade = {c: raiz_de(g) for c, g in grupo_de.items()}

    # --- divisão por unidade, estratificada pelo estrato majoritário da unidade ---
    grupos = defaultdict(list)
    for r in incluidas: grupos[unidade[r["caminho_relativo"]]].append(r)
    estratos = defaultdict(list)
    for g, ms in grupos.items():
        cont_e = Counter(estrato_de(m["caminho_relativo"], m["classe_original"]) for m in ms)
        classe = sorted(cont_e.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]   # empate: ordem alfabética
        estratos[classe].append((g, len(ms)))

    rnd = random.Random(a.semente)
    destino = {}
    for classe in sorted(estratos):
        lista = sorted(estratos[classe])            # ordem estável antes de embaralhar
        rnd.shuffle(lista)
        lista.sort(key=lambda x: -x[1])              # grupos grandes primeiro (sort estável)
        total = sum(n for _, n in lista); atual = Counter()
        for g, n in lista:
            s = max(SPLITS, key=lambda k: (prop[k] * total - atual[k]) / max(prop[k] * total, 1e-9))
            destino[g] = s; atual[s] += n

    linhas = [{"caminho_relativo": r["caminho_relativo"], "classe_original": r["classe_original"],
               "id_grupo": r["id_grupo"], "estrato": estrato_de(r["caminho_relativo"], r["classe_original"]),
               "fogo": rot.get(r["caminho_relativo"], {}).get("fogo", ""),
               "ambiente": rot.get(r["caminho_relativo"], {}).get("ambiente", ""),
               "unidade_divisao": unidade[r["caminho_relativo"]],
               "split": destino[unidade[r["caminho_relativo"]]]} for r in incluidas]
    linhas.sort(key=lambda x: (x["split"], x["estrato"], x["caminho_relativo"]))
    gravar(saida / "divisao.csv", linhas, ["caminho_relativo", "classe_original", "id_grupo", "unidade_divisao",
                                          "estrato", "fogo", "ambiente", "split"])
    gravar(saida / "pendentes.csv", pendentes, ["caminho_relativo", "classe_original", "id_grupo", "motivo", "decisao"])

    # --- resumo ---
    cont = Counter((l["split"], l["estrato"]) for l in linhas)
    tot_classe = Counter(l["estrato"] for l in linhas)
    resumo = [{"split": s, "estrato": c, "imagens": cont[(s, c)],
               "proporcao_do_estrato": round(cont[(s, c)] / tot_classe[c], 3)}
              for s in SPLITS for c in sorted(tot_classe)]
    gravar(saida / "resumo_divisao.csv", resumo, ["split", "estrato", "imagens", "proporcao_do_estrato"])

    # --- verificações de vazamento ---
    sha = {r["caminho_relativo"]: r["sha256"] for r in imagens}
    dh = {r["caminho_relativo"]: int(r["dhash"], 16) for r in imagens}
    msgs, ok = [], True
    g_splits = defaultdict(set); h_splits = defaultdict(set)
    for l in linhas:
        g_splits[l["id_grupo"]].add(l["split"]); h_splits[sha[l["caminho_relativo"]]].add(l["split"])
    viol_g = [g for g, s in g_splits.items() if len(s) > 1]
    viol_h = [h for h, s in h_splits.items() if len(s) > 1]
    msgs.append(f"grupos em mais de um split: {len(viol_g)} {'OK' if not viol_g else 'FALHA'}")
    msgs.append(f"arquivos identicos (SHA-256) em mais de um split: {len(viol_h)} {'OK' if not viol_h else 'FALHA'}")
    ok = not viol_g and not viol_h
    msgs.append(f"estratificacao: {a.estrato} | semente: {a.semente}")
    msgs.append(f"pares conferidos: {len(veredito)} | unioes por mesma_cena: {unidos}")
    msgs.append(f"imagens divididas: {len(linhas)} | pendentes/excluidas: {len(pendentes)} | total: {len(imagens)}")
    msgs.append(f"soma confere: {len(linhas) + len(pendentes) == len(imagens)}")

    pares = []
    for i in range(len(linhas)):
        hi = dh[linhas[i]["caminho_relativo"]]
        for j in range(i + 1, len(linhas)):
            if linhas[i]["split"] != linhas[j]["split"]:
                d = (hi ^ dh[linhas[j]["caminho_relativo"]]).bit_count()
                if d <= a.aviso:
                    v = veredito.get(frozenset((linhas[i]["caminho_relativo"], linhas[j]["caminho_relativo"])), "")
                    pares.append({"imagem_a": linhas[i]["caminho_relativo"], "split_a": linhas[i]["split"],
                                  "imagem_b": linhas[j]["caminho_relativo"], "split_b": linhas[j]["split"],
                                  "hamming": d, "veredito": v})
    pares.sort(key=lambda p: (p["hamming"], p["imagem_a"], p["imagem_b"]))
    split_de = {l["caminho_relativo"]: l["split"] for l in linhas}
    cand = []
    for i in range(len(linhas)):
        ci = linhas[i]["caminho_relativo"]; hi = dh[ci]
        for j in range(i + 1, len(linhas)):
            cj = linhas[j]["caminho_relativo"]
            if grupo_de[ci] != grupo_de[cj]:
                d = (hi ^ dh[cj]).bit_count()
                if d <= a.aviso:
                    cand.append({"imagem_a": ci, "split_a": split_de[ci], "imagem_b": cj, "split_b": split_de[cj],
                                 "hamming": d, "veredito": veredito.get(frozenset((ci, cj)), "")})
    cand.sort(key=lambda p: (p["hamming"], p["imagem_a"], p["imagem_b"]))
    gravar(saida / "pares_candidatos.csv", cand, ["imagem_a", "split_a", "imagem_b", "split_b", "hamming", "veredito"])
    gravar(saida / "pares_proximos_entre_splits.csv", pares,
           ["imagem_a", "split_a", "imagem_b", "split_b", "hamming", "veredito"])
    cv = Counter(p["veredito"] or "sem_revisao" for p in pares)
    msgs.append(f"pares parecidos (Hamming <= {a.aviso}) em splits diferentes: {len(pares)} | "
                f"cenas_diferentes: {cv['cenas_diferentes']} | sem revisao: {cv['sem_revisao']} | "
                f"mesma_cena (nao deveria ocorrer): {cv['mesma_cena']}")
    ok = ok and cv["mesma_cena"] == 0
    sem_cand = sum(1 for p in cand if not p["veredito"])
    msgs.append(f"pares candidatos (todos entre grupos diferentes, Hamming <= {a.aviso}): {len(cand)} | "
                f"sem veredito: {sem_cand}" + (" -> rode o 04b para conferir" if sem_cand else " -> todos conferidos"))
    (saida / "verificacao.txt").write_text("\n".join(msgs) + "\n", encoding="utf-8")

    print(f"Estratificação: {a.estrato}")
    print(f"{'estrato':32s} {'treino':>7s} {'validacao':>10s} {'teste':>7s}  total")
    for c in sorted(tot_classe):
        print(f"  {c:30s} " + " ".join(f"{cont[(s, c)]:>{w}d}" for s, w in zip(SPLITS, (7, 10, 7))) + f"  {tot_classe[c]:5d}")
    if a.estrato != "fogo":
        cf = Counter((l["split"], l["fogo"] or l["classe_original"]) for l in linhas)
        print("Por fogo:", {s: {f: cf[(s, f)] for f in sorted({k[1] for k in cf})} for s in SPLITS})
    print("\nVerificações:"); [print("  " + m) for m in msgs]
    print(f"\nSemente: {a.semente}. Nada foi alterado no dataset.")
    if not ok: raise SystemExit("VAZAMENTO DETECTADO - veja verificacao.txt")


if __name__ == "__main__":
    main()