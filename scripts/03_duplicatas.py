#!/usr/bin/env python3
"""
Etapa 3 - Duplicatas exatas e quase duplicatas (SOMENTE LEITURA).

Gera em relatorios/03_duplicatas/:
  imagem_grupo.csv   -> TODA imagem recebe um id_grupo (base da divisão sem vazamento, Etapa 4)
  grupos.csv         -> um registro por grupo: tipo (unica/exata/quase), tamanho, classes, conflito_rotulo
  conflitos_rotulo.csv -> grupos com imagens parecidas em classes originais DIFERENTES (ex.: fire x non_fire)
  sensibilidade.csv  -> quantos grupos/imagens "extras" surgem para cada limiar (ajuda a calibrar)
  folhas/*.png       -> folhas de contato dos grupos com 2+ imagens, para conferir visualmente

Nada é excluído: duplicatas só ganham o mesmo id_grupo.

Uso:  python scripts/03_duplicatas.py [--limiar 4]
"""
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError as exc:
    raise SystemExit("Dependência ausente: instale Pillow com 'python -m pip install Pillow'.") from exc

MINIATURA, COLS, LINS = 200, 6, 5


def dhash(img, n=8):
    g = img.convert("L").resize((n + 1, n), Image.Resampling.LANCZOS)
    px = list(g.tobytes())
    bits = 0
    for l in range(n):
        for c in range(n):
            bits = (bits << 1) | (1 if px[l * (n + 1) + c] > px[l * (n + 1) + c + 1] else 0)
    return bits


class UF:
    def __init__(self, n): self.p = list(range(n))
    def f(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]; x = self.p[x]
        return x
    def u(self, a, b):
        ra, rb = self.f(a), self.f(b)
        if ra != rb: self.p[rb] = ra


def agrupar(hashes, shas, limiar):
    n = len(hashes); uf = UF(n); por_sha = {}
    for i, s in enumerate(shas):
        if s in por_sha: uf.u(por_sha[s], i)
        else: por_sha[s] = i
    for i in range(n):
        for j in range(i + 1, n):
            if (hashes[i] ^ hashes[j]).bit_count() <= limiar:
                uf.u(i, j)
    return [uf.f(i) for i in range(n)]


def folha(itens, destino):
    img = Image.new("RGB", (COLS * MINIATURA, LINS * (MINIATURA + 16)), "white")
    d = ImageDraw.Draw(img)
    for i, (p, rotulo) in enumerate(itens):
        x, y = (i % COLS) * MINIATURA, (i // COLS) * (MINIATURA + 16)
        try:
            with Image.open(p) as im:
                im = im.convert("RGB"); im.thumbnail((MINIATURA - 4, MINIATURA - 4)); img.paste(im, (x + 2, y + 2))
        except Exception:
            d.rectangle([x + 2, y + 2, x + MINIATURA - 2, y + MINIATURA - 2], outline="red")
        d.text((x + 3, y + MINIATURA), rotulo[:34], fill="black")
    img.save(destino)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--origem", default="relatorios/01_origem/origem.json")
    ap.add_argument("--manifesto", default="relatorios/01_origem/manifesto_sha256.csv")
    ap.add_argument("--validacao", default="relatorios/02_validacao/validacao.csv")
    ap.add_argument("--saida", default="relatorios/03_duplicatas")
    ap.add_argument("--limiar", type=int, default=4, help="distância de Hamming (0-64) p/ quase duplicata")
    ap.add_argument("--max-folhas", type=int, default=12)
    a = ap.parse_args()

    raiz = Path(json.loads(Path(a.origem).read_text(encoding="utf-8"))["caminho_local"])
    sha = {r["caminho_relativo"]: r["sha256"] for r in csv.DictReader(open(a.manifesto, encoding="utf-8"))}
    imgs = [r for r in csv.DictReader(open(a.validacao, encoding="utf-8")) if r["situacao"] == "valida"]
    saida = Path(a.saida); (saida / "folhas").mkdir(parents=True, exist_ok=True)

    rels, classes, shas, hashes = [], [], [], []
    for r in imgs:
        with Image.open(raiz / r["caminho_relativo"]) as im:
            hashes.append(dhash(im))
        rels.append(r["caminho_relativo"]); classes.append(r["classe_original"]); shas.append(sha[r["caminho_relativo"]])

    # sensibilidade: quantos grupos com 2+ imagens para cada limiar
    sens = []
    for lim in (0, 2, 4, 6, 8, 10):
        raizes = agrupar(hashes, shas, lim); c = Counter(raizes)
        multi = [k for k, v in c.items() if v > 1]
        sens.append({"limiar": lim, "grupos_com_2_ou_mais": len(multi),
                     "imagens_em_grupos": sum(c[k] for k in multi), "maior_grupo": max(c.values())})
    with open(saida / "sensibilidade.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(sens[0].keys())); w.writeheader(); w.writerows(sens)

    raizes = agrupar(hashes, shas, a.limiar)
    membros = defaultdict(list)
    for i, r in enumerate(raizes): membros[r].append(i)
    ordem = sorted(membros.values(), key=lambda m: (-len(m), rels[m[0]]))
    gid = {}
    for k, m in enumerate(sorted(membros.values(), key=lambda m: rels[m[0]]), 1):
        for i in m: gid[i] = f"G{k:05d}"

    grupos, conflitos = [], []
    for m in ordem:
        g = gid[m[0]]; cls = sorted({classes[i] for i in m}); n_sha = len({shas[i] for i in m})
        tipo = "unica" if len(m) == 1 else ("exata" if n_sha == 1 else "quase")
        reg = {"id_grupo": g, "tipo": tipo, "n_imagens": len(m), "n_arquivos_distintos": n_sha,
               "classes": "|".join(cls), "conflito_rotulo": len(cls) > 1}
        grupos.append(reg)
        if len(cls) > 1:
            conflitos += [{"id_grupo": g, "caminho_relativo": rels[i], "classe_original": classes[i]} for i in m]

    def gravar(nome, linhas, cols):
        with open(saida / nome, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(linhas)
    gravar("grupos.csv", grupos, ["id_grupo", "tipo", "n_imagens", "n_arquivos_distintos", "classes", "conflito_rotulo"])
    gravar("conflitos_rotulo.csv", conflitos, ["id_grupo", "caminho_relativo", "classe_original"])
    gravar("imagem_grupo.csv",
           [{"caminho_relativo": rels[i], "classe_original": classes[i], "sha256": shas[i],
             "dhash": f"{hashes[i]:016x}", "id_grupo": gid[i]} for i in range(len(rels))],
           ["caminho_relativo", "classe_original", "sha256", "dhash", "id_grupo"])

    itens = [(raiz / rels[i], f"{gid[i]} {Path(rels[i]).name}") for m in ordem if len(m) > 1 for i in m]
    por_folha = COLS * LINS
    for k in range(0, min(len(itens), a.max_folhas * por_folha), por_folha):
        folha(itens[k:k + por_folha], saida / "folhas" / f"grupos_{k // por_folha + 1:02d}.png")

    print("Sensibilidade ao limiar (Hamming):")
    for s in sens:
        print(f"  limiar {s['limiar']:2d}: {s['grupos_com_2_ou_mais']:3d} grupos, "
              f"{s['imagens_em_grupos']:4d} imagens, maior grupo = {s['maior_grupo']}")
    tipos = Counter(g["tipo"] for g in grupos)
    print(f"\nLimiar usado: {a.limiar} | grupos: {len(grupos)} (únicos={tipos['unica']}, "
          f"exatos={tipos['exata']}, quase={tipos['quase']})")
    print(f"Grupos com conflito de rótulo (classes diferentes): {sum(g['conflito_rotulo'] for g in grupos)}")
    print("Nada foi alterado no dataset.")


if __name__ == "__main__":
    main()
