#!/usr/bin/env python3
"""
Etapa 15b - LINHA DE BASE SÓ COM COR (nenhuma imagem é alterada; não mexe nas redes da Etapa 12).

Pergunta: quanto do acerto de 99% vem só da cor? Um classificador simples que vê APENAS o histograma de cores
(HSV, 8 x 4 x 4 = 128 faixas, mais a fração de pixels "cor de chama") é treinado no MESMO treino, tem o limiar
calibrado na MESMA validação (F2, como na Etapa 12) e é medido no MESMO teste.

Como ler:
  * se a base de cor já chega perto das redes, o teste é fácil por cor e os 99% dizem pouco sobre "ver o fogo";
    os negativos difíceis (14b) e o teste em cinza (15c) passam a ser a medida que importa;
  * a distância entre a base de cor e a rede é o que a rede aprende além da cor (forma, textura, fumaça).

Entradas: data/treino_ignis/ (Etapa 11) e relatorios/12_treino/<rede>_torchvision/metricas_teste.json
Saídas  : relatorios/15_robustez/baseline_cor/ (resumo.txt, metricas.csv, predicoes_teste.csv)
Uso    : python scripts/15b_baseline_cor.py
Não precisa de placa de vídeo; leva poucos minutos (lê cada imagem uma vez).
"""
import argparse, csv, importlib.util, json, sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

RAIZ = Path(__file__).resolve().parent.parent
REDES = ("resnet18", "efficientnet_b0", "densenet121")


def t12():
    spec = importlib.util.spec_from_file_location("treino12", RAIZ / "scripts" / "12_treinar.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def descritor(caminho):
    with Image.open(caminho) as im:
        im = im.convert("RGB"); im.thumbnail((256, 256))
        hsv = np.asarray(im.convert("HSV"), dtype=np.float32) / 255.0
    h, s, v = hsv[..., 0].ravel(), hsv[..., 1].ravel(), hsv[..., 2].ravel()
    hist, _ = np.histogramdd(np.stack([h, s, v], 1), bins=(8, 4, 4), range=((0, 1), (0, 1), (0, 1)))
    hist = hist.ravel() / h.size
    chama = ((h < 0.14) | (h > 0.95)) & (s > 0.45) & (v > 0.55)   # vermelho-laranja-amarelo, saturado e claro
    return np.concatenate([np.sqrt(hist), [chama.mean(), v.mean(), s.mean()]])


def treinar_logistica(X, y, l2=1e-2, passos=3000, lr=0.5):
    """regressão logística com L2 e pesos por classe (o mesmo equilíbrio de classes do treino da Etapa 12)."""
    w = np.zeros(X.shape[1]); b = 0.0
    peso = np.where(y == 1, len(y) / (2 * y.sum()), len(y) / (2 * (len(y) - y.sum())))
    for _ in range(passos):
        p = 1 / (1 + np.exp(-(X @ w + b))); g = peso * (p - y)
        w -= lr * (X.T @ g / len(y) + l2 * w); b -= lr * g.mean()
    return w, b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dados", default="data/treino_ignis")
    ap.add_argument("--sufixo", default="torchvision")
    a = ap.parse_args()
    pasta = RAIZ / a.dados
    if not (pasta / "split_manifest.csv").is_file():
        sys.exit(f"[PARADO] Não achei {pasta / 'split_manifest.csv'}. Rode antes a Etapa 11.")
    T = t12()
    linhas = list(csv.DictReader((pasta / "split_manifest.csv").open(encoding="utf-8")))
    sai = RAIZ / "relatorios/15_robustez/baseline_cor"; sai.mkdir(parents=True, exist_ok=True)

    print(f"Lendo as cores de {len(linhas)} imagens...")
    F = np.stack([descritor(pasta / l["path"]) for l in linhas]); y = np.array([int(l["label"] == "Fire") for l in linhas])
    sp = np.array([l["split"] for l in linhas]); tr, va, te = sp == "train", sp == "val", sp == "test"
    mu, dp = F[tr].mean(0), F[tr].std(0) + 1e-6; Z = (F - mu) / dp
    w, b = treinar_logistica(Z[tr], y[tr])
    p = 1 / (1 + np.exp(-(Z @ w + b)))
    limiar = T.calibrar_limiar(y[va], p[va])
    mv, mt = T.metricas(y[va], p[va], limiar), T.metricas(y[te], p[te], limiar)
    mt["auc_roc"] = T.auc_roc(y[te], p[te])
    # só a fração de pixels cor de chama, com limiar na validação: a base mais ingênua possível
    pc = F[:, -3]; lc = T.calibrar_limiar(y[va], pc[va]); mc = T.metricas(y[te], pc[te], lc); mc["auc_roc"] = T.auc_roc(y[te], pc[te])

    tab = [("só pixels cor de chama", mc), ("histograma de cor (logística)", mt)]
    for rede in REDES:
        arq = RAIZ / "relatorios/12_treino" / f"{rede}_{a.sufixo}" / "metricas_teste.json"
        if arq.exists(): tab.append((f"{rede} (Etapa 12)", json.loads(arq.read_text(encoding="utf-8"))))
    f = lambda v: f"{100 * v:5.1f}%".replace(".", ",")
    res = [f"Etapa 15b | {datetime.now(timezone.utc).isoformat(timespec='seconds')} | linha de base só com cor",
           f"treino {tr.sum()} | validação {va.sum()} | teste {te.sum()} (o mesmo manifesto da Etapa 12)",
           f"limiar calibrado na validação (F2): histograma {limiar:.3f} | pixels de chama {lc:.4f}", "",
           f"  {'classificador':<32} {'acurácia':>9} {'recall fogo':>12} {'especific.':>11} {'AUC':>7}  VP/VN/FP/FN"]
    for nome, m in tab:
        res.append(f"  {nome:<32} {f(m['acuracia']):>9} {f(m['recall_fogo']):>12} {f(m['especificidade']):>11} "
                   f"{m.get('auc_roc', float('nan')):7.3f}  {m['vp']}/{m['vn']}/{m['fp']}/{m['fn']}")
    rede_ac = [m["acuracia"] for n, m in tab[2:]]
    if rede_ac:
        gap = 100 * (max(rede_ac) - mt["acuracia"])
        res += ["", f"Distância entre a melhor rede e a base de cor: {gap:.1f} pontos de acurácia.".replace(".", ",", 1)]
    res += ["", "Leitura: quanto menor a distância, mais o teste se resolve pela cor e menos os 99% mostram que a rede",
            "\"vê\" o fogo. Nesse caso, os negativos difíceis (Etapa 14b) e o teste em cinza (15c) são a medida principal."]
    (sai / "resumo.txt").write_text("\n".join(res) + "\n", encoding="utf-8")
    with (sai / "metricas.csv").open("w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh, lineterminator="\n"); wr.writerow(["classificador", "acuracia", "recall_fogo", "especificidade", "auc_roc", "vp", "vn", "fp", "fn"])
        for nome, m in tab: wr.writerow([nome] + [round(m.get(k, float("nan")), 4) for k in ("acuracia", "recall_fogo", "especificidade", "auc_roc")] + [m[k] for k in ("vp", "vn", "fp", "fn")])
    with (sai / "predicoes_teste.csv").open("w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh, lineterminator="\n"); wr.writerow(["path", "classe_real", "prob_fogo_cor", "fracao_pixels_chama", "acertou"])
        for k in np.where(te)[0]:
            wr.writerow([linhas[k]["path"], linhas[k]["label"], round(float(p[k]), 4), round(float(pc[k]), 4),
                         "sim" if (p[k] >= limiar) == bool(y[k]) else "nao"])
    print("\n".join(res)); print(f"\n[OK] {sai}")


if __name__ == "__main__":
    main()
