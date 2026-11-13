#!/usr/bin/env python3
"""
Etapa 10a - INVENTÁRIO DE UMA NOVA FONTE (SOMENTE LEITURA: nada é copiado, movido, renomeado ou apagado).

Serve para conhecer um dataset novo ANTES de decidir como integrá-lo. Para cada arquivo da nova fonte:
pasta, extensão, tamanho, dimensões, se abre, SHA-256 e dHash. Depois compara:
  * duplicatas dentro da nova fonte (SHA igual ou dHash a até --limiar bits, o mesmo critério da Etapa 3);
  * imagens da nova fonte que já existem (ou quase) no dataset atual.
Os nomes das pastas aparecem só como DESCRIÇÃO da fonte; não são usados como rótulo.

Saídas em relatorios/10_nova_fonte/<nome>/:
  arquivos.csv            -> uma linha por arquivo
  estrutura.csv           -> contagem por pasta x extensão
  duplicatas_internas.csv -> grupos com 2+ arquivos parecidos dentro da nova fonte
  duplicatas_com_atual.csv-> pares (nova, atual) com distância do dHash
  textos_encontrados.txt  -> início de README/LICENSE/txt/md/csv/json que vierem no download
  amostras.png            -> até 12 miniaturas sorteadas por pasta (semente fixa), para conferir a olho
  resumo.txt              -> tudo resumido

Uso:
  python scripts/10a_inventario_fonte.py --nova "C:\\...\\cristiancristancho\\forest-fire-image-dataset\\versions\\2"
         [--atual "C:\\...\\phylake1337\\fire-dataset\\versions\\1\\fire_dataset"] [--nome cristiancristancho_forest-fire] [--limiar 6]
"""
import argparse, csv, hashlib, random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageOps
    import numpy as np
except ImportError as exc:
    raise SystemExit("Dependência ausente (Pillow ou numpy). Use o .venv do projeto.") from exc

EXT_IMAGEM = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff", ".webp"}
EXT_TEXTO = {".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".xml", ""}
ATUAL_PADRAO = r"C:\Users\maria\.cache\kagglehub\datasets\phylake1337\fire-dataset\versions\1\fire_dataset"
POP = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint8)


def dhash(img, n=8):   # idêntico ao da Etapa 3
    g = img.convert("L").resize((n + 1, n), Image.Resampling.LANCZOS)
    px = list(g.tobytes())
    bits = 0
    for l in range(n):
        for c in range(n):
            bits = (bits << 1) | (1 if px[l * (n + 1) + c] > px[l * (n + 1) + c + 1] else 0)
    return bits


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""): h.update(bloco)
    return h.hexdigest()


def ler_imagem(p):
    """Devolve (info, dhash) sem alterar o arquivo."""
    info = {"legivel": "nao", "largura": "", "altura": "", "modo": "", "formato_real": "", "quadros": "", "erro": ""}
    try:
        with Image.open(p) as im:
            info.update(largura=im.width, altura=im.height, modo=im.mode, formato_real=im.format or "",
                        quadros=getattr(im, "n_frames", 1))
            im.load()
            h = dhash(im)
        info["legivel"] = "sim"
        return info, h
    except Exception as e:  # arquivo corrompido ou formato estranho: só registra
        info["erro"] = f"{type(e).__name__}: {e}"[:200]
        return info, None


def distancias(a, b):
    """Matriz de distâncias de Hamming entre dois vetores de hashes de 64 bits (uint64)."""
    x = np.bitwise_xor(a[:, None], b[None, :])
    return POP[x.view(np.uint8).reshape(*x.shape, 8)].sum(axis=-1)


def pares_proximos(ha, hb, limiar, mesma=False, bloco=500):
    for i0 in range(0, len(ha), bloco):
        d = distancias(ha[i0:i0 + bloco], hb)
        for i, j in zip(*np.nonzero(d <= limiar)):
            gi = i0 + i
            if mesma and j <= gi: continue
            yield gi, int(j), int(d[i, j])


def gravar(caminho, linhas, cols):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(linhas)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nova", required=True, help="pasta do download da nova fonte (só leitura)")
    ap.add_argument("--atual", default=ATUAL_PADRAO, help="pasta dos originais do dataset atual (só leitura)")
    ap.add_argument("--nome", default=None, help="nome curto da fonte (padrão: dono_dataset tirado do caminho)")
    ap.add_argument("--limiar", type=int, default=6)
    ap.add_argument("--saida", default="relatorios/10_nova_fonte")
    a = ap.parse_args()

    nova, atual = Path(a.nova), Path(a.atual)
    if not nova.is_dir(): raise SystemExit(f"Pasta da nova fonte não existe: {nova}")
    if not atual.is_dir(): raise SystemExit(f"Pasta do dataset atual não existe: {atual}")
    if a.nome is None:
        partes = nova.parts
        a.nome = f"{partes[-4]}_{partes[-3]}" if "versions" in partes else nova.name
    saida = Path(a.saida) / a.nome; saida.mkdir(parents=True, exist_ok=True)

    # 1) arquivos da nova fonte
    todos = sorted(p for p in nova.rglob("*") if p.is_file())
    linhas, hashes_n, idx_n, textos = [], [], [], []
    print(f"Nova fonte: {len(todos)} arquivos. Lendo (pode levar alguns minutos)...")
    for k, p in enumerate(todos, 1):
        rel = p.relative_to(nova)
        ext = p.suffix.lower()
        r = {"caminho_relativo": str(rel), "pasta": str(rel.parent), "extensao": ext, "bytes": p.stat().st_size,
             "sha256": sha256(p), "eh_imagem": "sim" if ext in EXT_IMAGEM else "nao", "dhash": ""}
        if ext in EXT_IMAGEM:
            info, h = ler_imagem(p)
            r.update(info)
            if h is not None:
                r["dhash"] = f"{h:016x}"; hashes_n.append(h); idx_n.append(len(linhas))
        else:
            r.update({"legivel": "", "largura": "", "altura": "", "modo": "", "formato_real": "", "quadros": "", "erro": ""})
            if ext in EXT_TEXTO and p.stat().st_size < 5_000_000: textos.append(p)
        linhas.append(r)
        if k % 500 == 0: print(f"  {k}/{len(todos)}")
    cols = ["caminho_relativo", "pasta", "extensao", "eh_imagem", "legivel", "formato_real", "largura", "altura",
            "modo", "quadros", "bytes", "sha256", "dhash", "erro"]
    gravar(saida / "arquivos.csv", linhas, cols)

    est = Counter((r["pasta"], r["extensao"]) for r in linhas)
    gravar(saida / "estrutura.csv", [{"pasta": p, "extensao": e, "arquivos": n} for (p, e), n in sorted(est.items())],
           ["pasta", "extensao", "arquivos"])

    # 2) duplicatas internas (SHA igual ou dHash próximo), agrupadas por união
    pai = list(range(len(linhas)))
    def f(x):
        while pai[x] != x: pai[x] = pai[pai[x]]; x = pai[x]
        return x
    def u(x, y):
        rx, ry = f(x), f(y)
        if rx != ry: pai[ry] = rx
    por_sha = {}
    for i, r in enumerate(linhas):
        if r["eh_imagem"] != "sim": continue
        if r["sha256"] in por_sha: u(por_sha[r["sha256"]], i)
        else: por_sha[r["sha256"]] = i
    hn = np.array(hashes_n, dtype=np.uint64)
    if len(hn):
        for i, j, _ in pares_proximos(hn, hn, a.limiar, mesma=True):
            u(idx_n[i], idx_n[j])
    grupos = defaultdict(list)
    for i, r in enumerate(linhas):
        if r["eh_imagem"] == "sim": grupos[f(i)].append(i)
    multi = [g for g in grupos.values() if len(g) > 1]
    dup_int = []
    for gid, g in enumerate(sorted(multi, key=len, reverse=True), 1):
        shas = {linhas[i]["sha256"] for i in g}
        for i in g:
            dup_int.append({"grupo": gid, "tamanho": len(g), "tipo": "exata" if len(shas) == 1 else "quase",
                            "pastas_no_grupo": " | ".join(sorted({linhas[x]["pasta"] for x in g})),
                            "caminho_relativo": linhas[i]["caminho_relativo"]})
    gravar(saida / "duplicatas_internas.csv", dup_int or [{}], ["grupo", "tamanho", "tipo", "pastas_no_grupo", "caminho_relativo"])

    # 3) comparação com o dataset atual
    atuais = sorted(p for p in atual.rglob("*") if p.is_file() and p.suffix.lower() in EXT_IMAGEM)
    print(f"Dataset atual: {len(atuais)} imagens. Calculando hashes para comparar...")
    sha_atual, h_atual, cam_atual = {}, [], []
    for p in atuais:
        s = sha256(p); sha_atual[s] = str(p.relative_to(atual))
        try:
            with Image.open(p) as im: h_atual.append(dhash(im)); cam_atual.append(str(p.relative_to(atual)))
        except Exception:
            pass
    ha = np.array(h_atual, dtype=np.uint64)
    com_atual = []
    for r in linhas:
        if r["eh_imagem"] == "sim" and r["sha256"] in sha_atual:
            com_atual.append({"nova": r["caminho_relativo"], "atual": sha_atual[r["sha256"]], "distancia": 0, "tipo": "exata (mesmo SHA)"})
    ja = {c["nova"] for c in com_atual}
    if len(hn) and len(ha):
        for i, j, d in pares_proximos(hn, ha, a.limiar):
            cam = linhas[idx_n[i]]["caminho_relativo"]
            if cam in ja and d == 0: continue
            com_atual.append({"nova": cam, "atual": cam_atual[j], "distancia": d, "tipo": "quase"})
    gravar(saida / "duplicatas_com_atual.csv", com_atual or [{}], ["nova", "atual", "distancia", "tipo"])
    novas_repetidas = {c["nova"] for c in com_atual}

    # 4) textos que vieram no download (licença, descrição, anotações)
    with open(saida / "textos_encontrados.txt", "w", encoding="utf-8") as f:
        if not textos: f.write("Nenhum arquivo de texto no download.\n")
        for p in textos:
            f.write(f"===== {p.relative_to(nova)} ({p.stat().st_size} bytes) =====\n")
            try: f.write(p.read_text(encoding="utf-8", errors="replace")[:3000] + "\n\n")
            except Exception as e: f.write(f"(não li: {e})\n\n")

    # 5) folha de amostras por pasta (semente fixa)
    rnd = random.Random(42)
    por_pasta = defaultdict(list)
    for r in linhas:
        if r["legivel"] == "sim": por_pasta[r["pasta"]].append(r["caminho_relativo"])
    M, N_POR = 160, 12
    pastas = sorted(por_pasta)[:20]
    folha = Image.new("RGB", (M * N_POR + 260, max(1, len(pastas)) * (M + 10) + 10), "white")
    dr = ImageDraw.Draw(folha)
    for li, pasta in enumerate(pastas):
        y = 10 + li * (M + 10)
        dr.text((8, y + 4), f"{pasta[:34]}\n({len(por_pasta[pasta])} imgs)", fill="black")
        amostra = rnd.sample(por_pasta[pasta], min(N_POR, len(por_pasta[pasta])))
        for ci, cam in enumerate(amostra):
            try:
                with Image.open(nova / cam) as im:
                    t = ImageOps.contain(im.convert("RGB"), (M, M))
                folha.paste(t, (260 + ci * M, y))
            except Exception:
                pass
    folha.save(saida / "amostras.png")

    # 6) resumo
    imgs = [r for r in linhas if r["eh_imagem"] == "sim"]
    leg = [r for r in imgs if r["legivel"] == "sim"]
    tam = Counter(f"{r['largura']}x{r['altura']}" for r in leg)
    fmt = Counter(f"{r['extensao']} -> {r['formato_real']}" for r in leg)
    menor = min((min(int(r["largura"]), int(r["altura"])) for r in leg), default=0)
    txt = [f"Etapa 10a gerada em {datetime.now(timezone.utc).isoformat(timespec='seconds')} | SOMENTE LEITURA",
           f"fonte: {a.nome}", f"pasta: {nova}", "",
           f"arquivos: {len(linhas)} | imagens: {len(imgs)} | abrem: {len(leg)} | não abrem: {len(imgs) - len(leg)}"
           f" | outros arquivos: {len(linhas) - len(imgs)}", "",
           "Por pasta (os nomes descrevem a fonte; NÃO viram rótulo):"]
    for pasta in sorted({r["pasta"] for r in linhas}):
        c = Counter(r["extensao"] for r in linhas if r["pasta"] == pasta)
        txt.append(f"  {pasta:50s} " + ", ".join(f"{e or '(sem ext)'} {n}" for e, n in c.most_common()))
    txt += ["", "Extensão -> formato real: " + "; ".join(f"{k} {v}" for k, v in fmt.most_common()),
            f"Tamanhos mais comuns: " + "; ".join(f"{k} ({v})" for k, v in tam.most_common(6)),
            f"Menor lado da menor imagem: {menor}px",
            f"Animadas/várias páginas (quadros > 1): {sum(1 for r in leg if str(r['quadros']) not in ('1', ''))}", "",
            f"Duplicatas internas (limiar {a.limiar}): {len(multi)} grupos, {sum(len(g) for g in multi)} imagens "
            f"({sum(len(g) - 1 for g in multi)} além da primeira de cada grupo)",
            f"Já existem no dataset atual: {len(novas_repetidas)} imagens da nova fonte "
            f"({sum(1 for c in com_atual if c['distancia'] == 0 and c['tipo'].startswith('exata'))} pares idênticos por SHA)",
            f"Arquivos de texto no download: {len(textos)} (ver textos_encontrados.txt; procurar a licença)", "",
            f"Arquivos em {saida}. Nada foi copiado, movido ou alterado."]
    (saida / "resumo.txt").write_text("\n".join(txt) + "\n", encoding="utf-8")
    print("\n".join(txt))


if __name__ == "__main__":
    main()
