#!/usr/bin/env python3
"""
Etapa 2 - Validação técnica e visual do dataset (SOMENTE LEITURA).

Lê o caminho do dataset em relatorios/01_origem/origem.json e gera em relatorios/02_validacao/:
  validacao.csv     -> uma linha por imagem (integridade, formato, dimensões, modo de cor, flags)
  resumo_classes.csv-> contagem por classe original e situação
  amostra_revisao.csv + folhas/*.png -> folhas de contato para conferir se o NOME DA PASTA
                                        corresponde ao conteúdo (revisão visual manual)

Uso:
  python scripts/02_validacao.py
  python scripts/02_validacao.py --folhas-completas non_fire_images   # revisar uma classe inteira
"""
import argparse, csv, json, random
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, UnidentifiedImageError

EXT_IMAGEM = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff", ".webp"}
LADO_MIN = 64          # abaixo disso a imagem é marcada como "muito pequena"
MINIATURA, COLS, LINS = 200, 6, 5


def classe_de(caminho, raiz):
    partes = caminho.relative_to(raiz).parts[:-1]
    return "/".join(partes) if partes else "(raiz)"


def validar(p):
    r = {"largura": "", "altura": "", "formato_real": "", "modo_cor": "", "situacao": "valida", "erro": ""}
    try:
        with Image.open(p) as im:
            im.verify()
        with Image.open(p) as im:
            im.load()
            r.update(largura=im.width, altura=im.height, formato_real=im.format or "", modo_cor=im.mode)
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as e:
        r.update(situacao="corrompida", erro=f"{type(e).__name__}: {e}")
    return r


def folha(imagens, destino, titulo):
    from PIL import ImageFont
    w, h = COLS * MINIATURA, LINS * (MINIATURA + 16)
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    for i, p in enumerate(imagens):
        x, y = (i % COLS) * MINIATURA, (i // COLS) * (MINIATURA + 16)
        try:
            with Image.open(p) as im:
                im = im.convert("RGB"); im.thumbnail((MINIATURA - 4, MINIATURA - 4))
                img.paste(im, (x + 2, y + 2))
        except Exception:
            d.rectangle([x + 2, y + 2, x + MINIATURA - 2, y + MINIATURA - 2], outline="red")
        d.text((x + 3, y + MINIATURA), f"{i+1}. {p.name}"[:34], fill="black")
    img.save(destino)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--origem", default="relatorios/01_origem/origem.json")
    ap.add_argument("--saida", default="relatorios/02_validacao")
    ap.add_argument("--amostra", type=int, default=60, help="imagens por classe nas folhas (padrão 60)")
    ap.add_argument("--folhas-completas", action="append", default=[], metavar="CLASSE")
    ap.add_argument("--semente", type=int, default=42)
    a = ap.parse_args()

    raiz = Path(json.loads(Path(a.origem).read_text(encoding="utf-8"))["caminho_local"])
    saida = Path(a.saida); (saida / "folhas").mkdir(parents=True, exist_ok=True)

    linhas, por_classe = [], {}
    for p in sorted(x for x in raiz.rglob("*") if x.is_file()):
        ext, classe = p.suffix.lower(), classe_de(p, raiz)
        if ext not in EXT_IMAGEM:
            linhas.append({"caminho_relativo": str(p.relative_to(raiz)), "nome_arquivo": p.name, "extensao": ext,
                           "classe_original": classe, "situacao": "nao_imagem", "largura": "", "altura": "",
                           "formato_real": "", "modo_cor": "", "flags": "", "erro": ""})
            continue
        r = validar(p)
        flags = []
        if r["situacao"] == "valida":
            if r["formato_real"].lower().replace("jpeg", "jpg") != ext.lstrip(".").replace("jpeg", "jpg"):
                flags.append("extensao_difere_do_formato")
            if min(r["largura"], r["altura"]) < LADO_MIN:
                flags.append("muito_pequena")
            if r["modo_cor"] not in ("RGB",):
                flags.append(f"modo_{r['modo_cor']}")
        linhas.append({"caminho_relativo": str(p.relative_to(raiz)), "nome_arquivo": p.name, "extensao": ext,
                       "classe_original": classe, "flags": ";".join(flags), **r})
        por_classe.setdefault(classe, []).append(p)

    cols = ["caminho_relativo", "nome_arquivo", "extensao", "classe_original", "situacao", "largura", "altura",
            "formato_real", "modo_cor", "flags", "erro"]
    with open(saida / "validacao.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(linhas)

    cont = Counter((l["classe_original"], l["situacao"]) for l in linhas)
    with open(saida / "resumo_classes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["classe_original", "situacao", "imagens"])
        for (c, s), q in sorted(cont.items()):
            w.writerow([c, s, q])

    rnd, amostra = random.Random(a.semente), []
    for classe, ps in por_classe.items():
        nome = classe.replace("/", "_")
        completa = classe in a.folhas_completas or Path(classe).name in a.folhas_completas
        escolhidas = ps if completa else rnd.sample(ps, min(a.amostra, len(ps)))
        escolhidas = sorted(escolhidas)
        for k in range(0, len(escolhidas), COLS * LINS):
            lote = escolhidas[k:k + COLS * LINS]
            folha(lote, saida / "folhas" / f"{nome}_{k // (COLS * LINS) + 1:02d}.png", classe)
        amostra += [{"classe_original": classe, "caminho_relativo": str(p.relative_to(raiz)),
                     "ambiente_visual": "", "fogo_visual": "", "fumaca_visual": "", "tipo_camera": "",
                     "observacao": ""} for p in escolhidas]
    with open(saida / "amostra_revisao.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(amostra[0].keys())); w.writeheader(); w.writerows(amostra)

    print("Resumo por classe e situação:")
    for (c, s), q in sorted(cont.items()):
        print(f"  {c:30s} {s:12s} {q}")
    print(f"Imagens com flags: {sum(1 for l in linhas if l['flags'])} | corrompidas: "
          f"{sum(l['situacao'] == 'corrompida' for l in linhas)}")
    print(f"Folhas de contato em {saida / 'folhas'} | revisão visual: preencha amostra_revisao.csv")
    print("Nada foi alterado no dataset.")


if __name__ == "__main__":
    main()
