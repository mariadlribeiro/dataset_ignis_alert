#!/usr/bin/env python3
"""
Etapa 13a - SELEÇÃO DO TESTE DE ATALHO (SOMENTE LEITURA: nada é copiado, movido ou rotulado).

Pergunta: o modelo acha fogo pela CHAMA ou pelo FORMATO da imagem?
No dataset, as 400 imagens da segunda fonte (quase todas quadradas e pequenas, 250x250) são todas SEM fogo.
Um modelo pode ter aprendido "quadrada e pequena = sem fogo". O teste do treino não separa isso, porque lá
todas as imagens desse formato são sem fogo.

Este script monta um teste EXTERNO, só para avaliação (nunca para treino), em que o formato não ajuda:
  * todas as imagens são da segunda fonte, de floresta, quadradas e pequenas (menor lado < 300 px);
  * metade sugerida COM fogo e metade SEM fogo (sugestão do CLIP da Etapa 10b; serve só para equilibrar);
  * nenhuma entrou no dataset nem na revisão da opção A;
  * nenhuma é quase igual (dHash <= --dist-min) a qualquer imagem do treino, validação ou teste;
  * dentro de cada metade, as mais diferentes entre si (k-centros, o mesmo da Etapa 10c).

A revisão é TODA cega (motivo "auditoria" no 05b): a pessoa não vê a sugestão, a pasta nem o caminho
antes de marcar. O rótulo do teste é o da revisão: fogo = chama visível; só fumaça = sem fogo.

Entradas: relatorios/10_nova_fonte/<nome>/sugestoes.csv, selecao_A/revisao.csv, data/treino_ignis/split_manifest.csv
Saídas  : relatorios/13_atalho/ (revisao.csv, sugestoes.csv, origem.json no formato do 05b; reserva.csv; resumo.txt)

Uso:
  python scripts/13a_selecao_atalho.py --nova "C:\\Users\\maria\\.cache\\kagglehub\\datasets\\cristiancristancho\\forest-fire-image-dataset\\versions\\2"
         [--por-classe 150] [--dist-min 10] [--semente 42]
"""
import argparse, csv, json, platform, random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import PIL
from PIL import Image

RAIZ = Path(__file__).resolve().parent.parent
NOME = "cristiancristancho_forest-fire-image-dataset"


def ler(c):
    with open(c, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def gravar(c, linhas, cols):
    with open(c, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(linhas)


def abrir(nova, rel):
    return Image.open(nova / Path(*rel.replace("\\", "/").split("/")))


def dhash(img):   # o mesmo da Etapa 11 (o manifesto do treino foi gravado com ele)
    g = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    px = g.tobytes(); bits = 0
    for lin in range(8):
        for col in range(8):
            bits = (bits << 1) | (px[lin * 9 + col] > px[lin * 9 + col + 1])
    return bits


def descritor(rgb):   # o mesmo da Etapa 10c
    g = np.asarray(rgb.convert("L").resize((16, 16), Image.Resampling.BILINEAR), dtype=np.float32).ravel() / 255
    p = np.asarray(rgb.resize((32, 32), Image.Resampling.BILINEAR), dtype=np.uint8).reshape(-1, 3) // 64
    h = np.bincount(p[:, 0] * 16 + p[:, 1] * 4 + p[:, 2], minlength=64).astype(np.float32); h /= h.sum()
    return np.concatenate([g / np.sqrt(len(g)), np.sqrt(h)])


def k_centros(X, k):
    k = min(k, len(X)); esc = [0]; dmin = np.linalg.norm(X - X[0], axis=1)
    while len(esc) < k:
        i = int(np.argmax(dmin)); esc.append(i); dmin = np.minimum(dmin, np.linalg.norm(X - X[i], axis=1))
    return esc


def formato_da_fonte(r):
    w, h = int(r["largura"]), int(r["altura"])
    return abs(w - h) / max(w, h) < 0.12 and min(w, h) < 300


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nova", required=True)
    ap.add_argument("--por-classe", type=int, default=150)
    ap.add_argument("--dist-min", type=int, default=10, help="dHash: até esta distância conta como quase igual ao dataset")
    ap.add_argument("--semente", type=int, default=42)
    ap.add_argument("--raiz-registrada", default=None, help="caminho a gravar no origem.json (ao rodar fora do Windows)")
    ap.add_argument("--saida", default="relatorios/13_atalho")
    a = ap.parse_args()

    nova = Path(a.nova)
    if not nova.is_dir(): raise SystemExit(f"Pasta da nova fonte não existe: {nova}")
    pasta10 = RAIZ / "relatorios/10_nova_fonte" / NOME
    sug = ler(pasta10 / "sugestoes.csv")
    ja_vistas = {r["caminho_relativo"] for r in ler(pasta10 / "selecao_A/revisao.csv")}
    man = ler(RAIZ / "data/treino_ignis/split_manifest.csv")
    dh_ds = np.array([int(m["dhash"], 16) for m in man], dtype=np.uint64)
    sai = RAIZ / a.saida; sai.mkdir(parents=True, exist_ok=True)

    reserva, pools = [], {"sim": [], "nao": []}
    for r in sug:
        cam = r["caminho_relativo"]
        if r["situacao"] != "candidata" or cam in ja_vistas:
            continue
        if r["ambiente_sugerido"] != "floresta" or r["fogo_sugerido"] not in pools or not formato_da_fonte(r):
            continue
        pools[r["fogo_sugerido"]].append(r)

    sel = {}
    for f, pool in pools.items():
        pool.sort(key=lambda r: r["caminho_relativo"])
        ok, X = [], []
        print(f"Sugerida {'com' if f == 'sim' else 'sem'} fogo: {len(pool)} candidatas no formato da fonte. Conferindo dHash...")
        for r in pool:
            with abrir(nova, r["caminho_relativo"]) as im:
                rgb = im.convert("RGB")
                d = int(min(bin(int(x)).count("1") for x in (dh_ds ^ np.uint64(dhash(rgb)))))
                if d <= a.dist_min:
                    reserva.append({"caminho_relativo": r["caminho_relativo"], "fogo_sugerido": f,
                                    "motivo": f"quase igual a uma imagem do dataset (dHash {d})"}); continue
                ok.append(r); X.append(descritor(rgb))
        idx = k_centros(np.stack(X), a.por_classe)
        sel[f] = [ok[i] for i in idx]
        escolhidas = {r["caminho_relativo"] for r in sel[f]}
        reserva += [{"caminho_relativo": r["caminho_relativo"], "fogo_sugerido": f,
                     "motivo": "reserva: não escolhida pela seleção de diversidade"} for r in ok if r["caminho_relativo"] not in escolhidas]

    # ordem embaralhada: a revisora não pode deduzir a classe pela posição
    todas = sel["sim"] + sel["nao"]
    random.Random(a.semente).shuffle(todas)
    sug_out, rev = [], []
    for n, r in enumerate(todas, 1):
        sug_out.append({**r, "classe_original": r["pasta"].replace("\\", "/"), "id_grupo": f"at{n:04d}", "split": "teste_atalho",
                        "camera_sugerida_fraca": "", "camera_conf": "", "motivos_revisao": "auditoria"})
        rev.append({"n": n, "caminho_relativo": r["caminho_relativo"], "classe_original": r["pasta"].replace("\\", "/"),
                    "motivos_revisao": "auditoria", "ambiente_sugerido": r["ambiente_sugerido"],
                    "fogo_sugerido": r["fogo_sugerido"], "fumaca_sugerida": r["fumaca_sugerida"],
                    "ambiente_confirmado": "", "fogo_confirmado": "", "fumaca_confirmada": "",
                    "camera_confirmada": "", "observacao": ""})
    gravar(sai / "sugestoes.csv", sug_out, list(sug_out[0].keys()))
    gravar(sai / "revisao.csv", rev, list(rev[0].keys()))
    gravar(sai / "reserva.csv", reserva, ["caminho_relativo", "fogo_sugerido", "motivo"])
    (sai / "origem.json").write_text(json.dumps({
        "dataset_ref": "cristiancristancho/forest-fire-image-dataset", "versao_kaggle": 2,
        "caminho_local": a.raiz_registrada or str(nova),
        "observacoes": "Teste de atalho (Etapa 13): só avaliação, nunca treino. A pasta da fonte não é rótulo."},
        indent=2, ensure_ascii=False), encoding="utf-8")

    tam = Counter(f"{r['largura']}x{r['altura']}" for r in todas)
    proximas = sum(1 for r in reserva if r["motivo"].startswith("quase"))
    txt = [f"Etapa 13a gerada em {datetime.now(timezone.utc).isoformat(timespec='seconds')} | SOMENTE LEITURA | seleção, não rótulos",
           f"python {platform.python_version()} | Pillow {PIL.__version__} | numpy {np.__version__} | semente {a.semente}", "",
           f"Candidatas de floresta, quadradas e pequenas, fora do dataset e da opção A: "
           f"{len(pools['sim'])} sugeridas com fogo, {len(pools['nao'])} sugeridas sem fogo",
           f"Descartadas por serem quase iguais a imagens do dataset (dHash <= {a.dist_min}): {proximas}",
           f"Selecionadas: {len(sel['sim'])} sugeridas com fogo + {len(sel['nao'])} sugeridas sem fogo = {len(todas)}, em ordem embaralhada",
           "  tamanhos: " + "; ".join(f"{k} ({v})" for k, v in tam.most_common(6)),
           "Revisão: toda cega. O rótulo final é o da revisão, não a sugestão.",
           f"Reserva (não selecionadas, com motivo): {len(reserva)} em reserva.csv", "",
           f"Arquivos em {sai}. Nada foi copiado, movido ou alterado."]
    (sai / "resumo.txt").write_text("\n".join(txt) + "\n", encoding="utf-8")
    print("\n".join(txt))


if __name__ == "__main__":
    main()
