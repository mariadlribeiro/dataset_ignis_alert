#!/usr/bin/env python3
"""
Etapa 15a - QUASE-DUPLICATAS POR SEMELHANÇA DE CONTEÚDO (nenhuma imagem é alterada; nada é treinado).

A Etapa 3 achou cópias por SHA-256 (iguais byte a byte) e por dHash (mesma foto recomprimida ou redimensionada).
O dHash não pega a MESMA CENA com outro recorte, espelhada, com filtro ou em outro quadro do mesmo vídeo. Se uma
dessas estiver no treino e a outra no teste, o teste fica mais fácil do que o uso real (vazamento).

Aqui cada imagem vira um vetor de conteúdo (CLIP, o mesmo modelo da Etapa 5a, ou DINOv2) e se compara cada par
das 1.388 imagens, das DUAS fontes. Saem os pares com semelhança de cosseno acima do limiar, separados em:
  * ENTRE SPLITS (treino x teste, treino x validação, validação x teste): possível vazamento, revisar primeiro;
  * no mesmo split: só redundância (pesa mais no treino, não infla o teste).
A página mostra cada par lado a lado; quem decide se é a mesma cena é uma pessoa.

Entrada : data/treino_ignis/ (Etapa 11: split_manifest.csv)
Saídas  : relatorios/15_robustez/duplicatas_<modelo>/ (pares.csv, resumo.txt, pares.html)
          data/embeddings/<modelo>.npz (cache dos vetores; fora do git)

Uso:
  python scripts/15a_duplicatas_embeddings.py                       (CLIP, limiar 0.95)
  python scripts/15a_duplicatas_embeddings.py --modelo facebook/dinov2-small --limiar 0.90
Depois abra relatorios\\15_robustez\\duplicatas_clip-vit-base-patch16\\pares.html no Chrome ou Edge.
"""
import argparse, csv, html, json, os, sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
ORDEM = {"train": 0, "val": 1, "test": 2}
NOME_SPLIT = {"train": "treino", "val": "validação", "test": "teste"}


def vetores(pasta, linhas, modelo, lote=16, falso=False):
    if falso:   # SÓ PARA TESTAR O SCRIPT: vetores aleatórios com alguns pares parecidos de propósito
        rng = np.random.default_rng(0); X = rng.normal(size=(len(linhas), 64))
        for k in range(0, len(X) - 1, 25): X[k + 1] = X[k] + rng.normal(scale=0.1, size=64)
        return X
    import torch
    from PIL import Image
    disp = "cuda" if torch.cuda.is_available() else "cpu"
    if "clip" in modelo.lower():
        from transformers import CLIPModel, CLIPProcessor
        m = CLIPModel.from_pretrained(modelo).to(disp).eval(); proc = CLIPProcessor.from_pretrained(modelo)
        def emb(ims):
            o = m.get_image_features(**proc(images=ims, return_tensors="pt").to(disp))
            return o if torch.is_tensor(o) else o.pooler_output
    else:
        from transformers import AutoImageProcessor, AutoModel
        m = AutoModel.from_pretrained(modelo).to(disp).eval(); proc = AutoImageProcessor.from_pretrained(modelo)
        def emb(ims):
            h = m(**proc(images=ims, return_tensors="pt").to(disp)).last_hidden_state
            return torch.cat([h[:, 0], h[:, 1:].mean(1)], 1)   # CLS + média dos patches
    X = []
    with torch.no_grad():
        for k in range(0, len(linhas), lote):
            ims = []
            for l in linhas[k:k + lote]:
                with Image.open(pasta / l["path"]) as im: ims.append(im.convert("RGB"))
            X.append(emb(ims).float().cpu().numpy())
            print(f"  vetores {min(k + lote, len(linhas))}/{len(linhas)}", end="\r")
    print()
    return np.concatenate(X)


def dist_dhash(a, b):
    try: return bin(int(a, 16) ^ int(b, 16)).count("1")
    except (ValueError, TypeError): return ""


def pagina(pares, pasta_img, saida, titulo):
    rel = Path(os.path.relpath(pasta_img, saida.parent)).as_posix()
    blocos = []
    for n, p in enumerate(pares, 1):
        cor = "#b4321e" if p["tipo"] == "entre_splits" else "#5a6b63"
        img = lambda c: f'<figure><img loading="lazy" src="{html.escape(rel + "/" + c)}"><figcaption>{html.escape(c)}</figcaption></figure>'
        blocos.append(f'<section><h2 style="color:{cor}">{n}. {p["sim"]:.3f} · {html.escape(p["rotulo"])}'
                      f' · dHash {p["dhash"]}</h2><div class="par">{img(p["a"])}{img(p["b"])}</div></section>')
    saida.write_text(f"""<!DOCTYPE html><html lang="pt-BR"><meta charset="utf-8"><title>{html.escape(titulo)}</title>
<style>body{{font:15px system-ui;margin:24px;background:#fbfaf6;color:#0f1f19}}section{{margin:0 0 28px}}
h2{{font-size:15px;margin:0 0 6px}}.par{{display:flex;gap:12px}}figure{{margin:0;flex:1}}
img{{width:100%;max-height:340px;object-fit:contain;background:#e8e6df}}figcaption{{font-size:12px;color:#5a6b63;word-break:break-all}}</style>
<h1>{html.escape(titulo)}</h1><p>Vermelho: par entre splits (possível vazamento). Cinza: mesmo split. Se for a mesma cena,
anote o par para juntar os dois no mesmo grupo de duplicatas.</p>{''.join(blocos)}</html>""", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dados", default="data/treino_ignis")
    ap.add_argument("--modelo", default="openai/clip-vit-base-patch16")
    ap.add_argument("--limiar", type=float, default=0.95, help="semelhança de cosseno mínima para listar o par")
    ap.add_argument("--max-pagina", type=int, default=300, help="pares na página (os de maior semelhança)")
    ap.add_argument("--teste-sem-modelo", action="store_true", help="vetores aleatórios, só para testar o script")
    a = ap.parse_args()

    pasta = RAIZ / a.dados
    if not (pasta / "split_manifest.csv").is_file():
        sys.exit(f"[PARADO] Não achei {pasta / 'split_manifest.csv'}. Rode antes a Etapa 11 (11_exportar_treino.py).")
    linhas = list(csv.DictReader((pasta / "split_manifest.csv").open(encoding="utf-8")))
    curto = a.modelo.split("/")[-1] + ("_falso" if a.teste_sem_modelo else "")
    sai = RAIZ / "relatorios/15_robustez" / f"duplicatas_{curto}"; sai.mkdir(parents=True, exist_ok=True)
    cache = RAIZ / "data/embeddings" / f"{curto}.npz"; cache.parent.mkdir(parents=True, exist_ok=True)

    shas = np.array([l["sha256"] for l in linhas])
    if cache.exists() and np.array_equal(np.load(cache)["sha256"], shas):
        X = np.load(cache)["X"]; print(f"Vetores do cache {cache}")
    else:
        print(f"Calculando vetores de {len(linhas)} imagens com {a.modelo}...")
        X = vetores(pasta, linhas, a.modelo, falso=a.teste_sem_modelo); np.savez_compressed(cache, X=X, sha256=shas)
    X = X / np.linalg.norm(X, axis=1, keepdims=True)
    S = X @ X.T; np.fill_diagonal(S, -1)

    pares = []
    for i, j in zip(*np.where(np.triu(S, 1) >= a.limiar)):
        la, lb = linhas[i], linhas[j]
        if ORDEM[la["split"]] > ORDEM[lb["split"]]: la, lb = lb, la
        mesmo_grupo = la["group_key"] == lb["group_key"]
        tipo = "mesmo_grupo" if mesmo_grupo else ("entre_splits" if la["split"] != lb["split"] else "mesmo_split")
        pares.append({"sim": float(S[i, j]), "tipo": tipo, "a": la["path"], "b": lb["path"],
                      "split_a": la["split"], "split_b": lb["split"], "classe_a": la["label"], "classe_b": lb["label"],
                      "fonte_a": la["source_id"], "fonte_b": lb["source_id"], "grupo_a": la["group_key"], "grupo_b": lb["group_key"],
                      "dhash": dist_dhash(la.get("dhash"), lb.get("dhash")),
                      "rotulo": f"{NOME_SPLIT[la['split']]} × {NOME_SPLIT[lb['split']]}, {la['label']} × {lb['label']}"})
    pares.sort(key=lambda p: (p["tipo"] != "entre_splits", -p["sim"]))
    cols = ["sim", "tipo", "a", "b", "split_a", "split_b", "classe_a", "classe_b", "fonte_a", "fonte_b", "grupo_a", "grupo_b", "dhash"]
    with (sai / "pares.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols + ["mesma_cena"], extrasaction="ignore", lineterminator="\n"); w.writeheader()
        for p in pares: w.writerow(p | {"sim": round(p["sim"], 4), "mesma_cena": ""})
    novos = [p for p in pares if p["tipo"] != "mesmo_grupo"]
    pagina(novos[:a.max_pagina], pasta, sai / "pares.html", f"Quase-duplicatas por conteúdo ({a.modelo}, cosseno ≥ {a.limiar})")

    # para cada imagem de TESTE: a mais parecida no treino (mostra quão "perto" o teste está do treino)
    tr = np.array([l["split"] == "train" for l in linhas]); te = np.array([l["split"] == "test" for l in linhas])
    viz = S[np.ix_(te, tr)].max(1)
    c = Counter(p["tipo"] for p in pares)
    cruz = Counter((p["split_a"], p["split_b"]) for p in pares if p["tipo"] == "entre_splits")
    fontes = Counter(p["fonte_a"] != p["fonte_b"] for p in novos)
    res = [f"Etapa 15a | {datetime.now(timezone.utc).isoformat(timespec='seconds')} | {a.modelo} | cosseno ≥ {a.limiar}"
           + (" | TESTE SEM MODELO: números falsos" if a.teste_sem_modelo else ""),
           f"{len(linhas)} imagens | {len(pares)} pares acima do limiar", "",
           f"  ENTRE SPLITS (possível vazamento, revisar): {c['entre_splits']}"]
    res += [f"    {NOME_SPLIT[s1]} × {NOME_SPLIT[s2]}: {k}" for (s1, s2), k in sorted(cruz.items())]
    res += [f"  mesmo split, grupos diferentes (redundância): {c['mesmo_split']}",
            f"  já no mesmo grupo da Etapa 3 (confirma o dHash): {c['mesmo_grupo']}",
            f"  pares novos entre as duas fontes: {fontes[True]}", "",
            "Imagem de teste x a mais parecida do treino (cosseno):",
            f"  mediana {np.median(viz):.3f} | 90% abaixo de {np.quantile(viz, .9):.3f} | máximo {viz.max():.3f}",
            f"  testes com vizinho no treino ≥ {a.limiar}: {int((viz >= a.limiar).sum())} de {te.sum()}", "",
            "Leitura: cada par ENTRE SPLITS confirmado como mesma cena deve ir para o mesmo grupo (e o mesmo split) e o",
            "teste deve ser medido de novo sem ele. Zero pares confirmados = o teste não tem vazamento por cena repetida.",
            "Anote a decisão na coluna mesma_cena de pares.csv (sim/nao)."]
    (sai / "resumo.txt").write_text("\n".join(res) + "\n", encoding="utf-8")
    (sai / "config.json").write_text(json.dumps({"modelo": a.modelo, "limiar": a.limiar, "imagens": len(linhas)}, indent=2), encoding="utf-8")
    print("\n".join(res)); print(f"\n[OK] {sai}")


if __name__ == "__main__":
    main()
