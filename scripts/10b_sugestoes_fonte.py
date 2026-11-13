#!/usr/bin/env python3
"""
Etapa 10b - SUGESTÕES de ambiente, fogo e fumaça para a NOVA FONTE (SOMENTE LEITURA).

O modelo NÃO decide nada: só sugere, para sabermos quantas candidatas existem em cada tipo de cena antes de
planejar a revisão humana. Usa exatamente as mesmas frases, o mesmo modelo e os mesmos limiares da Etapa 5a
(o código é carregado de scripts/05a_sugestoes.py). O nome da pasta da fonte NÃO entra na sugestão.

Quem é candidata: imagem que abre, com 1 quadro, que NÃO existe (nem quase) no dataset atual. De cada grupo de
duplicatas internas, só a primeira é analisada; as outras ficam registradas com o motivo. Nada é excluído.

Entradas (geradas pela 10a): relatorios/10_nova_fonte/<nome>/arquivos.csv, duplicatas_internas.csv,
                             duplicatas_com_atual.csv
Saídas na mesma pasta:
  sugestoes.csv          -> uma linha por arquivo da fonte: situação e, para as candidatas, as sugestões
  contagem.txt           -> candidatas por ambiente x fogo sugeridos (e por tamanho de imagem)
  folhas_sugestoes/*.png -> 30 miniaturas sorteadas (semente fixa) de cada combinação ambiente|fogo
  parcial_sugestoes.json -> progresso; se o script for interrompido, é só rodar de novo que ele continua

Uso:
  python scripts/10b_sugestoes_fonte.py --nova "C:\\...\\forest-fire-image-dataset\\versions\\2"
         [--nome cristiancristancho_forest-fire-image-dataset] [--teste-sem-modelo]
"""
import argparse, csv, importlib.util, json, random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

BLOCO = 500


def carregar_05a():
    p = Path(__file__).with_name("05a_sugestoes.py")
    if not p.exists(): raise SystemExit(f"Não achei {p} (preciso das frases e limiares da Etapa 5a).")
    spec = importlib.util.spec_from_file_location("sug05a", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def ler(caminho):
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def gravar(caminho, linhas, cols):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(linhas)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nova", required=True)
    ap.add_argument("--nome", default=None)
    ap.add_argument("--saida", default="relatorios/10_nova_fonte")
    ap.add_argument("--modelo", default="openai/clip-vit-base-patch16")
    ap.add_argument("--semente", type=int, default=42)
    ap.add_argument("--teste-sem-modelo", action="store_true")
    a = ap.parse_args()

    nova = Path(a.nova)
    if not nova.is_dir(): raise SystemExit(f"Pasta da nova fonte não existe: {nova}")
    if a.nome is None:
        partes = nova.parts
        a.nome = f"{partes[-4]}_{partes[-3]}" if "versions" in partes else nova.name
    pasta = Path(a.saida) / a.nome
    if not (pasta / "arquivos.csv").exists(): raise SystemExit(f"Rode antes a 10a: falta {pasta / 'arquivos.csv'}")
    s5 = carregar_05a()
    LIM, nomes_amb = s5.LIM, list(s5.AMBIENTES)

    arquivos = ler(pasta / "arquivos.csv")
    ja_temos = {r["nova"] for r in ler(pasta / "duplicatas_com_atual.csv") if r.get("nova")}
    grupo = {}
    for r in ler(pasta / "duplicatas_internas.csv"):
        if r.get("caminho_relativo"): grupo[r["caminho_relativo"]] = r["grupo"]
    visto = set()
    for r in arquivos:   # arquivos.csv está em ordem alfabética: a primeira de cada grupo é a representante
        cam = r["caminho_relativo"]; r["grupo_interno"] = grupo.get(cam, "")
        if r["eh_imagem"] != "sim": r["situacao"] = "fora: não é imagem"
        elif r["legivel"] != "sim": r["situacao"] = "fora: não abre"
        elif str(r["quadros"]) not in ("1", ""): r["situacao"] = "fora: animada ou várias páginas"
        elif cam in ja_temos: r["situacao"] = "fora: já existe no dataset atual"
        elif cam in grupo and grupo[cam] in visto: r["situacao"] = "fora: duplicata interna (outra do grupo foi analisada)"
        else:
            r["situacao"] = "candidata"
            if cam in grupo: visto.add(grupo[cam])
    # se um grupo interno encosta no dataset atual, o grupo todo já é "conhecido"
    grupos_conhecidos = {grupo[c] for c in ja_temos if c in grupo}
    for r in arquivos:
        if r["situacao"] == "candidata" and r["grupo_interno"] in grupos_conhecidos:
            r["situacao"] = "fora: grupo de duplicatas que já existe no dataset atual"
    cand = [r for r in arquivos if r["situacao"] == "candidata"]
    print(f"Arquivos: {len(arquivos)} | candidatas: {len(cand)} | modelo: {'(teste)' if a.teste_sem_modelo else a.modelo}")
    print("Situação:", dict(Counter(r["situacao"] for r in arquivos)))

    # previsões em blocos, com retomada
    parcial = pasta / ("parcial_sugestoes_teste.json" if a.teste_sem_modelo else "parcial_sugestoes.json")
    feito = json.loads(parcial.read_text(encoding="utf-8")) if parcial.exists() else {}
    if feito: print(f"Retomando: {len(feito)} imagens já analisadas.")
    falta = [r["caminho_relativo"] for r in cand if r["caminho_relativo"] not in feito]
    meta = {}
    for k in range(0, len(falta), BLOCO):
        lote = falta[k:k + BLOCO]
        cams = [nova / c for c in lote]
        pred, meta = s5.prever_falso(cams) if a.teste_sem_modelo else s5.prever_clip(cams, a.modelo)
        for c, p in zip(lote, pred): feito[c] = p
        parcial.write_text(json.dumps(feito), encoding="utf-8")
        print(f"bloco concluído: {len(feito)}/{len(cand)} candidatas analisadas")

    for r in cand:
        p = feito[r["caminho_relativo"]]
        ordem = sorted(range(len(nomes_amb)), key=lambda i: -p["amb"][i])
        t1, t2 = ordem[0], ordem[1]
        conf, margem = p["amb"][t1], p["amb"][t1] - p["amb"][t2]
        r.update({"ambiente_sugerido": nomes_amb[t1] if (conf >= LIM["amb_conf_min"] and margem >= LIM["amb_margem_min"]) else "ambiente_incerto",
                  "amb_top1": nomes_amb[t1], "amb_conf": round(conf, 3), "amb_top2": nomes_amb[t2], "amb_margem": round(margem, 3),
                  "fogo_sugerido": s5.tri(p["fogo"]), "fogo_prob": round(p["fogo"], 3),
                  "fumaca_sugerida": s5.tri(p["fumaca"]), "fumaca_prob": round(p["fumaca"], 3)})
    cols = ["caminho_relativo", "pasta", "situacao", "grupo_interno", "largura", "altura", "ambiente_sugerido", "amb_top1",
            "amb_conf", "amb_top2", "amb_margem", "fogo_sugerido", "fogo_prob", "fumaca_sugerida", "fumaca_prob", "sha256"]
    gravar(pasta / "sugestoes.csv", arquivos, cols)

    # contagens
    ambs = [x for x in nomes_amb + ["ambiente_incerto"] if any(r["ambiente_sugerido"] == x for r in cand)]
    cel = Counter((r["ambiente_sugerido"], r["fogo_sugerido"]) for r in cand)
    txt = [f"Etapa 10b gerada em {datetime.now(timezone.utc).isoformat(timespec='seconds')} | SOMENTE LEITURA | SUGESTÕES, não rótulos",
           f"fonte: {a.nome} | modelo: {meta.get('modelo', '(retomado do parcial)')}", "",
           "Situação dos arquivos:"]
    txt += [f"  {n:6d}  {s}" for s, n in Counter(r["situacao"] for r in arquivos).most_common()]
    txt += ["", f"Candidatas ({len(cand)}) por ambiente sugerido x fogo sugerido:",
            f"  {'ambiente':18s} {'sim':>6s} {'nao':>6s} {'incerto':>8s} {'total':>7s}"]
    for amb in ambs:
        v = [cel[(amb, f)] for f in ("sim", "nao", "incerto")]
        txt.append(f"  {amb:18s} {v[0]:6d} {v[1]:6d} {v[2]:8d} {sum(v):7d}")
    txt += ["", "Fumaça sugerida entre as candidatas SEM fogo sugerido (possíveis cenas de fumaça sem chama):",
            "  " + str(dict(Counter(r["fumaca_sugerida"] for r in cand if r["fogo_sugerido"] == "nao"))),
            "", "Candidatas de FLORESTA por tamanho de imagem (tamanhos repetidos costumam ser quadros de vídeo):"]
    tam = Counter((f"{r['largura']}x{r['altura']}", r["fogo_sugerido"]) for r in cand if r["ambiente_sugerido"] == "floresta")
    tot = Counter()
    for (t, _), n in tam.items(): tot[t] += n
    for t, n in tot.most_common(8):
        txt.append(f"  {t:12s} total {n:5d} | sim {tam[(t, 'sim')]:5d} | nao {tam[(t, 'nao')]:5d} | incerto {tam[(t, 'incerto')]:5d}")
    txt += ["", "Sugestão x pasta da fonte (só para ver discordâncias; a pasta NÃO é rótulo):",
            "  " + str(dict(Counter((Path(r["pasta"]).name, r["fogo_sugerido"]) for r in cand))),
            "", f"Arquivos em {pasta}. Nada foi copiado, movido ou alterado."]
    (pasta / "contagem.txt").write_text("\n".join(txt) + "\n", encoding="utf-8")

    # folhas de amostra por combinação
    dest = pasta / "folhas_sugestoes"; dest.mkdir(exist_ok=True)
    rnd = random.Random(a.semente)
    por = defaultdict(list)
    for r in cand: por[(r["ambiente_sugerido"], r["fogo_sugerido"])].append(r)
    M, C, L = 200, 6, 5
    for (amb, fogo), itens in sorted(por.items()):
        am = rnd.sample(itens, min(C * L, len(itens)))
        img = Image.new("RGB", (C * M, 24 + L * (M + 14)), "white"); d = ImageDraw.Draw(img)
        d.text((4, 4), f"SUGESTAO: ambiente={amb} | fogo={fogo} | {len(itens)} candidatas (amostra de {len(am)})", fill="black")
        for i, r in enumerate(am):
            x, y = (i % C) * M, 24 + (i // C) * (M + 14)
            try:
                with Image.open(nova / r["caminho_relativo"]) as im:
                    img.paste(ImageOps.contain(im.convert("RGB"), (M - 4, M - 4)), (x + 2, y + 2))
            except Exception:
                d.rectangle([x + 2, y + 2, x + M - 2, y + M - 2], outline="red")
            d.text((x + 3, y + M - 2), Path(r["caminho_relativo"]).name[:32], fill="black")
        img.save(dest / f"{amb}__fogo_{fogo}.png")

    print("\n" + "\n".join(txt))


if __name__ == "__main__":
    main()
