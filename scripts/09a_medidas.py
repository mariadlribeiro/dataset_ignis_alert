#!/usr/bin/env python3
"""
Etapa 9a - MEDIDAS AUTOMÁTICAS de cada imagem (SOMENTE LEITURA: lê os originais, não altera nada).

Mede o que dá para medir sem ninguém olhar. Essas medidas não viram rótulo de treino: servem para ver
lacunas no dataset (ex.: quase nenhuma imagem escura no teste) e, depois do treino, para medir o erro
por condição (o modelo erra mais em imagens escuras? desfocadas? pequenas?).

Para as medidas serem comparáveis entre imagens de tamanhos diferentes, cada imagem é reduzida na
memória para 512 px no lado maior antes de medir brilho, contraste, saturação, nitidez e tons de fogo.

Colunas:
  largura, altura, megapixels, proporcao       -> do arquivo original
  brilho        0 a 255  média da luminância (escuro < 70; claro > 170, como referência)
  contraste     0 a 128  desvio-padrão da luminância
  saturacao     0 a 255  média da saturação (HSV)
  nitidez       >= 0     variância do Laplaciano: valores baixos indicam imagem borrada
  pct_escuro    %        pixels com luminância < 40
  pct_estourado %        pixels com luminância > 245
  pct_tons_fogo %        pixels laranja/amarelo/vermelho, saturados e claros. HEURÍSTICA: pôr do sol
                         e luz artificial também contam; não é detector de fogo.
  faixa_brilho, faixa_nitidez -> faixas por quartil (q1 a q4) calculadas no próprio dataset
  iluminacao    escura (brilho < --limite-escura, padrão 70), clara (brilho >= --limite-clara, padrão 110)
                ou media. É a iluminação da IMAGEM (clara ou escura), não a hora do dia.
  pct_quente    %        pixels de tom quente (vermelho a amarelo) com alguma saturação
  preto_e_branco sim/nao saturação média < 12 (foto sem cor)
  orientacao    paisagem (proporção > 1,1), retrato (< 0,9) ou quadrada
  cor1..cor3, pct_cor1..pct_cor3 -> as 3 cores dominantes (hex) e quanto da imagem cada uma ocupa
  formato       formato real do arquivo (JPEG, PNG, ...)
  jpeg_qualidade_est 1 a 100  qualidade estimada da compressão JPEG pelas tabelas de quantização
                         (vazio se não for JPEG). Valores baixos = mais artefatos de compressão.
  tem_exif, camera_exif  se o arquivo guarda dados da câmera, e qual câmera (fabricante e modelo)
  moldura       nenhuma, barras_horizontais, barras_verticais ou moldura: faixas lisas pretas/brancas nas
                bordas (comuns em captura de vídeo e montagem); pct_borda = % da área ocupada por elas.
                Conservador: barras coladas em áreas muito escuras (céu de noite) podem passar sem ser marcadas
  pct_ceu_est   %  estimativa de quanto da METADE DE CIMA da imagem parece céu (azul, ou claro e sem cor).
                HEURÍSTICA: céu de noite ou coberto de fumaça escura não conta
  pct_bordas    %  densidade de bordas (Sobel): cena "carregada" (cidade, galhos) x "limpa" (céu, campo)
  ruido         nível de ruído estimado (método de Immerkær): valores altos = imagem granulada
  blocos_jpeg   razão entre a diferença de pixels nas fronteiras de 8 px e fora delas, no tamanho original;
                acima de 1,5 os "quadradinhos" da compressão JPEG costumam ficar visíveis (blocos_visiveis = sim)
  pct_maior_foco %  área da MAIOR mancha contínua de tons de fogo (ajuda a conferir a distância do fogo)

Também gera folha_iluminacao.png: 8 exemplos sorteados de cada faixa, para conferir os limites a olho.

Entradas : relatorios/01_origem/origem.json (onde estão os originais) e relatorios/06_plano/inventario.csv
Saídas   : relatorios/09_condicoes/medidas_auto.csv  (só as imagens incluídas na divisão)
           relatorios/09_condicoes/folha_iluminacao.png

Uso:  python scripts/09a_medidas.py
"""
import argparse, csv, json, random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

LADO = 512
# tabela de quantização de luminância padrão do JPEG (IJG, qualidade 50); a ordem não importa: usamos a soma
TAB_LUM = [16, 11, 10, 16, 24, 40, 51, 61, 12, 12, 14, 19, 26, 58, 60, 55, 14, 13, 16, 24, 40, 57, 69, 56,
           14, 17, 22, 29, 51, 87, 80, 62, 18, 22, 37, 56, 68, 109, 103, 77, 24, 35, 55, 64, 81, 104, 113, 92,
           49, 64, 78, 87, 103, 121, 120, 101, 72, 92, 95, 98, 112, 100, 103, 99]


def qualidade_jpeg(im):
    q = getattr(im, "quantization", None)
    if not q or 0 not in q:
        return ""
    escala = 100 * sum(q[0]) / sum(TAB_LUM)          # % da tabela padrão
    if escala <= 0:
        return 100
    qual = (200 - escala) / 2 if escala <= 100 else 5000 / escala
    return int(round(min(100, max(1, qual))))


def exif_camera(im):
    try:
        ex = im.getexif()
    except Exception:
        return "nao", ""
    if not ex:
        return "nao", ""
    cam = " ".join(str(ex.get(t, "")).strip("\x00 ") for t in (271, 272)).strip()   # Make, Model
    return "sim", cam


def cores_dominantes(rgb, n=3):
    pequena = rgb.copy(); pequena.thumbnail((128, 128))
    q = pequena.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette(); cont = sorted(q.getcolors(), reverse=True)
    total = sum(c for c, _ in cont); out = {}
    for i in range(n):
        if i < len(cont):
            c, idx = cont[i]; r, g, b = pal[3 * idx: 3 * idx + 3]
            out[f"cor{i + 1}"], out[f"pct_cor{i + 1}"] = f"#{r:02x}{g:02x}{b:02x}", round(100 * c / total, 1)
        else:
            out[f"cor{i + 1}"], out[f"pct_cor{i + 1}"] = "", ""
    return out


def ler(caminho):
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def gravar(caminho, linhas, cols):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(linhas)


def moldura(L, lim_frac=0.02):
    """Conta linhas/colunas lisas (desvio < 2) e quase pretas ou brancas a partir de cada borda."""
    def corre(seq):
        n = 0
        for linha in seq:
            m, d = float(linha.mean()), float(linha.std())
            if d < 2 and (m < 10 or m > 245): n += 1
            else: break
        # barra de verdade termina num degrau nítido; noite ou céu liso vão escurecendo aos poucos
        if 0 < n < len(seq) - 3:
            depois = seq[n:n + 3]
            if abs(float(depois.mean()) - float(seq[n - 1].mean())) < 12 and float(depois.std()) < 4:
                return 0
        return n
    h, w = L.shape
    t, b = corre(L), corre(L[::-1])
    e, d = corre(L.T), corre(L.T[::-1])
    hor = t >= lim_frac * h and b >= lim_frac * h
    ver = e >= lim_frac * w and d >= lim_frac * w
    tipo = "moldura" if hor and ver else "barras_horizontais" if hor else "barras_verticais" if ver else "nenhuma"
    area = 1 - ((h - t - b) * (w - e - d)) / (h * w) if tipo != "nenhuma" else 0.0
    return tipo, round(100 * max(area, 0.0), 1)


def ruido(L):
    """Desvio do ruído pelo método de Immerkær (1996)."""
    M = (L[:-2, :-2] - 2 * L[:-2, 1:-1] + L[:-2, 2:] - 2 * L[1:-1, :-2] + 4 * L[1:-1, 1:-1] - 2 * L[1:-1, 2:]
         + L[2:, :-2] - 2 * L[2:, 1:-1] + L[2:, 2:])
    h, w = L.shape
    return float(np.sqrt(np.pi / 2) * np.abs(M).sum() / (6 * (w - 2) * (h - 2)))


def blocos_jpeg(Lorig):
    """Diferença média nas fronteiras de 8 px / diferença média fora delas (num recorte central de até 1024 px)."""
    h, w = Lorig.shape
    y0, x0 = max(0, (h - 1024) // 2) // 8 * 8, max(0, (w - 1024) // 2) // 8 * 8
    A = Lorig[y0:y0 + 1024, x0:x0 + 1024]
    dx = np.abs(np.diff(A, axis=1))
    if dx.shape[1] < 16:
        return ""
    col = np.arange(dx.shape[1])
    fronteira = (col % 8) == 7
    dentro = dx[:, ~fronteira].mean()
    return round(float(dx[:, fronteira].mean() / dentro), 3) if dentro > 0 else ""


def maior_mancha(mascara, lado=128):
    """% da imagem ocupada pela maior região conectada (vizinhança de 4) da máscara, numa grade reduzida."""
    h, w = mascara.shape
    fy, fx = max(1, h // lado), max(1, w // lado)
    m = mascara[:h // fy * fy, :w // fx * fx].reshape(h // fy, fy, w // fx, fx).mean(axis=(1, 3)) > 0.5
    vis = np.zeros_like(m, dtype=bool); melhor = 0
    H, W = m.shape
    for y in range(H):
        for x in range(W):
            if m[y, x] and not vis[y, x]:
                pilha = [(y, x)]; vis[y, x] = True; n = 0
                while pilha:
                    a, b = pilha.pop(); n += 1
                    for c, d in ((a + 1, b), (a - 1, b), (a, b + 1), (a, b - 1)):
                        if 0 <= c < H and 0 <= d < W and m[c, d] and not vis[c, d]:
                            vis[c, d] = True; pilha.append((c, d))
                melhor = max(melhor, n)
    return round(100 * melhor / m.size, 2)


def medir(caminho):
    with Image.open(caminho) as im:
        largura, altura = im.size
        formato = im.format or ""
        qual = qualidade_jpeg(im) if formato in ("JPEG", "MPO") else ""
        tem_exif, camera = exif_camera(im)
        im.seek(0)                                  # GIF/MPO: primeiro quadro
        im = ImageOps.exif_transpose(im) if hasattr(ImageOps, "exif_transpose") else im
        rgb = im.convert("RGB")
    Lorig = np.asarray(rgb.convert("L"), dtype=np.float64)
    rgb.thumbnail((LADO, LADO), Image.LANCZOS)
    L = np.asarray(rgb.convert("L"), dtype=np.float64)
    hsv = np.asarray(rgb.convert("HSV"), dtype=np.float64)
    H, S, V = hsv[..., 0] * 360 / 255, hsv[..., 1], hsv[..., 2]
    lap = (-4 * L[1:-1, 1:-1] + L[:-2, 1:-1] + L[2:, 1:-1] + L[1:-1, :-2] + L[1:-1, 2:])
    fogo = ((H <= 50) | (H >= 345)) & (S >= 100) & (V >= 150)
    tipo_mold, pct_borda = moldura(L)
    metade = slice(0, L.shape[0] // 2)
    ceu = (((H[metade] >= 180) & (H[metade] <= 250) & (S[metade] >= 30) & (V[metade] >= 100))
           | ((S[metade] < 40) & (V[metade] > 170)))
    gy, gx = np.gradient(L)
    bj = blocos_jpeg(Lorig)
    return {"largura": largura, "altura": altura, "megapixels": round(largura * altura / 1e6, 3),
            "proporcao": round(largura / altura, 3),
            "brilho": round(float(L.mean()), 1), "contraste": round(float(L.std()), 1),
            "saturacao": round(float(S.mean()), 1), "nitidez": round(float(lap.var()), 1),
            "pct_escuro": round(100 * float((L < 40).mean()), 2), "pct_estourado": round(100 * float((L > 245).mean()), 2),
            "pct_tons_fogo": round(100 * float(fogo.mean()), 2),
            "pct_quente": round(100 * float((((H <= 60) | (H >= 330)) & (S >= 60)).mean()), 2),
            "preto_e_branco": "sim" if float(S.mean()) < 12 else "nao",
            "orientacao": "paisagem" if largura / altura > 1.1 else ("retrato" if largura / altura < 0.9 else "quadrada"),
            **cores_dominantes(rgb), "formato": formato, "jpeg_qualidade_est": qual,
            "tem_exif": tem_exif, "camera_exif": camera,
            "moldura": tipo_mold, "pct_borda": pct_borda,
            "pct_ceu_est": round(100 * float(ceu.mean()), 1),
            "pct_bordas": round(100 * float((np.hypot(gx, gy) > 20).mean()), 1),
            "ruido": round(ruido(L), 2), "blocos_jpeg": bj,
            "blocos_visiveis": ("sim" if bj != "" and bj > 1.5 else "nao") if bj != "" else "",
            "pct_maior_foco": maior_mancha(fogo)}


def folha(linhas, raiz, destino, por=8, lado=180):
    """8 exemplos sorteados (semente 42) de cada faixa de iluminação, uma faixa por linha."""
    rnd = random.Random(42)
    faixas = ("escura", "media", "clara")
    img = Image.new("RGB", (110 + por * lado, len(faixas) * (lado + 18)), "white")
    d = ImageDraw.Draw(img)
    for i, f in enumerate(faixas):
        grupo = [l for l in linhas if l["iluminacao"] == f]
        y = i * (lado + 18)
        d.text((6, y + lado // 2), f"{f} ({len(grupo)})", fill="black")
        for j, l in enumerate(rnd.sample(grupo, min(por, len(grupo)))):
            with Image.open(raiz / l["caminho_original"].replace("\\", "/")) as im:
                im.seek(0); t = im.convert("RGB"); t.thumbnail((lado - 4, lado - 4))
            x = 110 + j * lado
            img.paste(t, (x + 2, y + 2)); d.text((x + 3, y + lado + 2), f"brilho {l['brilho']}", fill="black")
    img.save(destino)


def quartis(valores):
    q = np.percentile(valores, [25, 50, 75])
    return lambda v: "q1" if v <= q[0] else "q2" if v <= q[1] else "q3" if v <= q[2] else "q4"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--origem", default="relatorios/01_origem/origem.json")
    ap.add_argument("--inventario", default="relatorios/06_plano/inventario.csv")
    ap.add_argument("--saida", default="relatorios/09_condicoes")
    ap.add_argument("--limite-escura", type=float, default=70.0)
    ap.add_argument("--limite-clara", type=float, default=110.0)
    ap.add_argument("--usar-copia", action="store_true",
                    help="lê cada imagem da cópia organizada (coluna destino); serve para o inventário combinado, com mais de uma fonte")
    a = ap.parse_args()

    raiz = Path(json.loads(Path(a.origem).read_text(encoding="utf-8"))["caminho_local"])
    inv = [r for r in ler(a.inventario) if r["situacao"] == "incluida"]
    linhas, falhas = [], []
    for i, r in enumerate(inv, 1):
        k = r["caminho_original"]
        try:
            m = medir(Path(r["destino"]) if a.usar_copia else raiz / k.replace("\\", "/"))
        except Exception as e:
            falhas.append(f"{k}: {e}"); continue
        linhas.append({"caminho_original": k, "sha256": r["sha256"], "split": r["split"],
                       "ambiente": r["ambiente"], "fogo": r["fogo"], **m})
        print(f"  {i}/{len(inv)}", end="\r")
    print()
    if falhas:
        raise SystemExit(f"{len(falhas)} imagens não puderam ser lidas (nada foi gravado):\n  " + "\n  ".join(falhas[:20]))

    fb, fn = quartis([l["brilho"] for l in linhas]), quartis([l["nitidez"] for l in linhas])
    for l in linhas:
        l["faixa_brilho"], l["faixa_nitidez"] = fb(l["brilho"]), fn(l["nitidez"])
        l["iluminacao"] = ("escura" if l["brilho"] < a.limite_escura else
                           "clara" if l["brilho"] >= a.limite_clara else "media")
    saida = Path(a.saida); saida.mkdir(parents=True, exist_ok=True)
    gravar(saida / "medidas_auto.csv", linhas, list(linhas[0].keys()))

    def resumo(campo):
        v = np.array([l[campo] for l in linhas])
        return f"{campo:14s} mediana {np.median(v):8.1f} | 10% {np.percentile(v, 10):8.1f} | 90% {np.percentile(v, 90):8.1f}"
    print(f"Imagens medidas: {len(linhas)} (só as incluídas na divisão)")
    for c in ("megapixels", "brilho", "contraste", "saturacao", "nitidez", "pct_escuro", "pct_tons_fogo"):
        print("  " + resumo(c))
    for s in ("treino", "validacao", "teste"):
        sub = [l for l in linhas if l["split"] == s]
        esc = sum(l["brilho"] < 70 for l in sub)
        print(f"  {s:10s} {len(sub):4d} imagens | escuras (brilho < 70): {esc:3d} ({100 * esc / max(len(sub), 1):.0f}%)")
    print(f"  iluminação (escura < {a.limite_escura:g} <= media < {a.limite_clara:g} <= clara):")
    for s in ("treino", "validacao", "teste"):
        sub = [l for l in linhas if l["split"] == s]
        c = {k: sum(l["iluminacao"] == k for l in sub) for k in ("escura", "media", "clara")}
        print(f"    {s:10s} " + " | ".join(f"{k} {v:3d} ({100 * v / max(len(sub), 1):2.0f}%)" for k, v in c.items()))
    from collections import Counter
    print("  orientação:", dict(Counter(l["orientacao"] for l in linhas)), "| preto e branco:", sum(l["preto_e_branco"] == "sim" for l in linhas))
    qs = [l["jpeg_qualidade_est"] for l in linhas if l["jpeg_qualidade_est"] != ""]
    if qs:
        print(f"  qualidade JPEG estimada: mediana {int(np.median(qs))} | abaixo de 50: {sum(q < 50 for q in qs)} de {len(qs)}")
    print("  com dados de câmera (EXIF):", sum(l["camera_exif"] != "" for l in linhas))
    print("  moldura/barras:", dict(Counter(l["moldura"] for l in linhas)), "| blocos JPEG visíveis:", sum(l["blocos_visiveis"] == "sim" for l in linhas))
    for c in ("pct_ceu_est", "pct_bordas", "ruido", "pct_maior_foco"):
        v = np.array([l[c] for l in linhas], dtype=float)
        print(f"  {c:14s} mediana {np.median(v):8.1f} | 10% {np.percentile(v, 10):8.1f} | 90% {np.percentile(v, 90):8.1f}")
    if a.usar_copia:
        print(f"Arquivo: {saida / 'medidas_auto.csv'} (a folha de iluminação não é gerada com --usar-copia). Nada no dataset foi alterado.")
        return
    folha(linhas, raiz, saida / "folha_iluminacao.png")
    print(f"Arquivos: {saida / 'medidas_auto.csv'} e {saida / 'folha_iluminacao.png'}. Nada no dataset foi alterado.")


if __name__ == "__main__":
    main()
