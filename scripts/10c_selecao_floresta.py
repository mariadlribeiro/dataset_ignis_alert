#!/usr/bin/env python3
"""
Etapa 10c - SELEÇÃO para revisão: floresta SEM fogo da nova fonte (SOMENTE LEITURA).

Objetivo (opção A, aprovada em 12/11/2026): empatar a floresta do dataset (510 com fogo x 231 sem fogo).
Este script NÃO rotula nem copia nada. Ele só escolhe QUAIS candidatas vão para a revisão humana:

  1. floresta sem fogo: entre as candidatas com sugestão ambiente=floresta e fogo=nao (Etapa 10b), escolhe
     --alvo imagens o mais DIFERENTES possível entre si (seleção gulosa "k-centros" sobre uma miniatura 16x16
     + histograma de cor). Isso evita encher a revisão de quadros quase iguais do mesmo vídeo.
  2. possíveis confusores: candidatas em que a sugestão de fogo discorda da pasta da fonte (ex.: fogos de
     artifício, pôr do sol). A pasta NÃO vira rótulo; a discordância só serve para chamar a revisão.
  3. auditoria cega: uma fração das selecionadas de floresta é marcada como 'auditoria' (sugestão escondida).

Tudo que não for selecionado vai para nao_selecionadas.csv com o motivo. Nada é excluído.

Saídas em relatorios/10_nova_fonte/<nome>/selecao_A/:
  origem.json, sugestoes.csv, revisao.csv  -> no formato que o 05b_pagina_revisao.py lê
  nao_selecionadas.csv                     -> candidatas que ficaram de reserva, com motivo
  folhas/selecao_XX.png                    -> miniaturas na ordem do revisao.csv
  resumo.txt

Uso:
  python scripts/10c_selecao_floresta.py --nova "C:\\...\\forest-fire-image-dataset\\versions\\2"
         [--alvo 350] [--confusores 60] [--auditoria 0.15] [--semente 42]
"""
import argparse, csv, json, platform, random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import PIL
from PIL import Image, ImageDraw, ImageOps

CAMERAS = ["satelite", "drone", "vigilancia", "celular_terrestre"]   # mesma ordem da Etapa 5a


def ler(caminho):
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def gravar(caminho, linhas, cols):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(linhas)


def abrir(nova, rel):
    return Image.open(nova / Path(*rel.replace("\\", "/").split("/")))


def descritor(nova, rel):
    """Miniatura 16x16 em cinza (forma da cena) + histograma de cor 4x4x4 (paleta). Tudo em 0..1."""
    with abrir(nova, rel) as im:
        rgb = im.convert("RGB")
        g = np.asarray(rgb.convert("L").resize((16, 16), Image.Resampling.BILINEAR), dtype=np.float32).ravel() / 255
        p = np.asarray(rgb.resize((32, 32), Image.Resampling.BILINEAR), dtype=np.uint8).reshape(-1, 3) // 64
    h = np.bincount(p[:, 0] * 16 + p[:, 1] * 4 + p[:, 2], minlength=64).astype(np.float32); h /= h.sum()
    return np.concatenate([g / np.sqrt(len(g)), np.sqrt(h)])   # as duas partes têm norma parecida


def k_centros(X, k, inicio=0):
    """Seleção gulosa: cada nova imagem é a mais distante de todas as já escolhidas. Determinística."""
    k = min(k, len(X))
    escolhidas = [inicio]
    dmin = np.linalg.norm(X - X[inicio], axis=1)
    while len(escolhidas) < k:
        i = int(np.argmax(dmin)); escolhidas.append(i)
        dmin = np.minimum(dmin, np.linalg.norm(X - X[i], axis=1))
    return escolhidas, dmin


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nova", required=True)
    ap.add_argument("--nome", default=None)
    ap.add_argument("--saida", default="relatorios/10_nova_fonte")
    ap.add_argument("--alvo", type=int, default=350, help="quantas de floresta sem fogo vão para a revisão")
    ap.add_argument("--confusores", type=int, default=60)
    ap.add_argument("--auditoria", type=float, default=0.15)
    ap.add_argument("--semente", type=int, default=42)
    ap.add_argument("--raiz-registrada", default=None,
                    help="caminho da nova fonte a gravar no origem.json (use quando rodar fora do Windows)")
    ap.add_argument("--dataset-ref", default="cristiancristancho/forest-fire-image-dataset")
    a = ap.parse_args()

    nova = Path(a.nova)
    if not nova.is_dir(): raise SystemExit(f"Pasta da nova fonte não existe: {nova}")
    raiz_reg = a.raiz_registrada or str(nova)
    if a.nome is None:
        partes = raiz_reg.replace("\\", "/").rstrip("/").split("/")
        a.nome = f"{partes[-4]}_{partes[-3]}" if "versions" in partes else partes[-1]
    pasta = Path(a.saida) / a.nome
    sug = ler(pasta / "sugestoes.csv")
    parcial = json.loads((pasta / "parcial_sugestoes.json").read_text(encoding="utf-8"))
    cand = [r for r in sug if r["situacao"] == "candidata"]
    sai = pasta / "selecao_A"; (sai / "folhas").mkdir(parents=True, exist_ok=True)

    # 1) floresta sem fogo: as mais diferentes entre si
    pool = sorted((r for r in cand if r["ambiente_sugerido"] == "floresta" and r["fogo_sugerido"] == "nao"),
                  key=lambda r: r["caminho_relativo"])
    print(f"Floresta sem fogo sugerida: {len(pool)} candidatas. Calculando descritores...")
    X = np.stack([descritor(nova, r["caminho_relativo"]) for r in pool])
    idx, _ = k_centros(X, a.alvo)
    sel_flo = [pool[i] for i in idx]
    escolhidas = {r["caminho_relativo"] for r in sel_flo}
    # distância de cada selecionada à selecionada mais parecida (para a revisora ver possíveis repetidas)
    S = X[idx]; D = np.linalg.norm(S[:, None] - S[None, :], axis=2); np.fill_diagonal(D, 9)
    viz = {sel_flo[i]["caminho_relativo"]: (sel_flo[int(D[i].argmin())]["caminho_relativo"], float(D[i].min())) for i in range(len(sel_flo))}

    # 2) possíveis confusores: sugestão de fogo discorda da pasta da fonte
    def pasta_diz_fogo(r): return "NON_FIRE" not in r["pasta"].upper()
    disc_nao = sorted((r for r in cand if pasta_diz_fogo(r) and r["fogo_sugerido"] == "nao" and r["caminho_relativo"] not in escolhidas),
                      key=lambda r: r["caminho_relativo"])
    disc_sim = sorted((r for r in cand if not pasta_diz_fogo(r) and r["fogo_sugerido"] == "sim"), key=lambda r: r["caminho_relativo"])
    sel_conf = disc_nao[:a.confusores]
    resto = a.confusores - len(sel_conf)
    if resto > 0 and disc_sim:
        Xc = np.stack([descritor(nova, r["caminho_relativo"]) for r in disc_sim])
        ic, _ = k_centros(Xc, resto)
        sel_conf += [disc_sim[i] for i in ic]
    conf_set = {r["caminho_relativo"] for r in sel_conf}

    # 3) auditoria cega entre as de floresta
    rnd = random.Random(a.semente)
    aud = {r["caminho_relativo"] for r in rnd.sample(sel_flo, int(len(sel_flo) * a.auditoria))}

    # arquivos no formato do 05b
    sug_out, rev = [], []
    ordem = sorted(sel_flo, key=lambda r: (r["caminho_relativo"] in aud, r["caminho_relativo"])) + sel_conf
    ordem = [r for r in ordem if r["caminho_relativo"] not in aud] + [r for r in ordem if r["caminho_relativo"] in aud]
    for n, r in enumerate(ordem, 1):
        cam = r["caminho_relativo"]; p = parcial[cam]
        ic = max(range(len(CAMERAS)), key=lambda i: p["cam"][i])
        motivo = "auditoria" if cam in aud else ("discorda_da_pasta" if cam in conf_set else "nova_fonte_floresta_sem_fogo")
        sug_out.append({**r, "classe_original": r["pasta"].replace("\\", "/"), "id_grupo": f"nf{n:04d}", "split": "",
                        "camera_sugerida_fraca": CAMERAS[ic], "camera_conf": round(p["cam"][ic], 3),
                        "motivos_revisao": motivo, "mais_parecida_na_selecao": viz.get(cam, ("", 0))[0],
                        "distancia_mais_parecida": round(viz.get(cam, ("", 0))[1], 3)})
        rev.append({"n": n, "caminho_relativo": cam, "classe_original": r["pasta"].replace("\\", "/"), "motivos_revisao": motivo,
                    "ambiente_sugerido": r["ambiente_sugerido"], "fogo_sugerido": r["fogo_sugerido"],
                    "fumaca_sugerida": r["fumaca_sugerida"], "ambiente_confirmado": "", "fogo_confirmado": "",
                    "fumaca_confirmada": "", "camera_confirmada": "", "observacao": ""})
    gravar(sai / "sugestoes.csv", sug_out, list(sug_out[0].keys()))
    gravar(sai / "revisao.csv", rev, list(rev[0].keys()))
    (sai / "origem.json").write_text(json.dumps({
        "dataset_ref": a.dataset_ref, "url": f"https://www.kaggle.com/datasets/{a.dataset_ref}", "versao_kaggle": 2,
        "caminho_local": raiz_reg, "licenca": "A CONFERIR na página do Kaggle (o download não trouxe arquivo de licença)",
        "observacoes": "Seleção da opção A (floresta sem fogo). A pasta da fonte não é usada como rótulo."},
        indent=2, ensure_ascii=False), encoding="utf-8")

    sel_tudo = {r["caminho_relativo"] for r in ordem}
    fora = []
    for r in cand:
        if r["caminho_relativo"] in sel_tudo: continue
        eh_pool = r["ambiente_sugerido"] == "floresta" and r["fogo_sugerido"] == "nao"
        fora.append({"caminho_relativo": r["caminho_relativo"], "ambiente_sugerido": r["ambiente_sugerido"],
                     "fogo_sugerido": r["fogo_sugerido"],
                     "motivo": "reserva: floresta sem fogo sugerida, não escolhida pela seleção de diversidade (opção A)" if eh_pool
                     else "reserva: fora do alvo da opção A (não é floresta sem fogo sugerida)"})
    gravar(sai / "nao_selecionadas.csv", fora, ["caminho_relativo", "ambiente_sugerido", "fogo_sugerido", "motivo"])

    M, C, L = 200, 6, 5
    for k in range(0, len(rev), C * L):
        img = Image.new("RGB", (C * M, L * (M + 14)), "white"); d = ImageDraw.Draw(img)
        for i, s in enumerate(rev[k:k + C * L]):
            x, y = (i % C) * M, (i // C) * (M + 14)
            try:
                with abrir(nova, s["caminho_relativo"]) as im:
                    img.paste(ImageOps.contain(im.convert("RGB"), (M - 4, M - 4)), (x + 2, y + 2))
            except Exception:
                d.rectangle([x + 2, y + 2, x + M - 2, y + M - 2], outline="red")
            d.text((x + 3, y + M - 2), f"{s['n']}. {s['motivos_revisao'][:22]}", fill="black")
        img.save(sai / "folhas" / f"selecao_{k // (C * L) + 1:02d}.png")

    tam = Counter(f"{r['largura']}x{r['altura']}" for r in sel_flo)
    txt = [f"Etapa 10c gerada em {datetime.now(timezone.utc).isoformat(timespec='seconds')} | SOMENTE LEITURA | seleção para revisão, não rótulos",
           f"fonte: {a.dataset_ref} | python {platform.python_version()} | Pillow {PIL.__version__} | numpy {np.__version__} | semente {a.semente}",
           "", f"Floresta sem fogo sugerida: {len(pool)} candidatas -> {len(sel_flo)} selecionadas por diversidade (k-centros)",
           "  tamanhos das selecionadas: " + "; ".join(f"{k} ({v})" for k, v in tam.most_common(8)),
           f"Possíveis confusores (sugestão discorda da pasta): {len(sel_conf)} "
           f"({sum(1 for r in sel_conf if r['fogo_sugerido'] == 'nao')} pasta FIRE sem fogo sugerido, "
           f"{sum(1 for r in sel_conf if r['fogo_sugerido'] == 'sim')} pasta NON_FIRE com fogo sugerido)",
           f"Auditoria cega: {len(aud)} das {len(sel_flo)} de floresta",
           f"TOTAL para revisar: {len(rev)} | ficaram de reserva: {len(fora)} (nao_selecionadas.csv)",
           "", f"Arquivos em {sai}. Nada foi copiado, movido ou alterado."]
    (sai / "resumo.txt").write_text("\n".join(txt) + "\n", encoding="utf-8")
    print("\n".join(txt))


if __name__ == "__main__":
    main()
