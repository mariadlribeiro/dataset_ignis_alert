#!/usr/bin/env python3
"""
Etapa 15c - TESTE EM TONS DE CINZA (nenhuma imagem é alterada no disco; nada é treinado).

As MESMAS 207 imagens de teste passam pelas redes da Etapa 12 duas vezes: coloridas e convertidas para cinza
(a cinza é repetida nos três canais, a rede recebe o mesmo formato). O limiar é o calibrado na validação.

Como ler:
  * se o recall de fogo despenca em cinza, a rede depende quase só da cor (laranja = fogo); isso combina com os
    falsos alarmes de pôr do sol da Etapa 14b;
  * se cai pouco, a rede também usa forma e textura da chama e da fumaça.
A rede nunca viu imagem cinza no treino, então alguma queda é esperada: o que interessa é o tamanho dela e quais
imagens mudam (predicoes_<rede>.csv, coluna mudou).

Entradas: data/treino_ignis/ (Etapa 11), data/modelos/<rede>_torchvision/modelo.pth, relatorios/12_treino/
Saídas  : relatorios/15_robustez/cinza/ (resumo.txt, metricas.csv, predicoes_<rede>.csv)
Uso    : python scripts/15c_teste_cinza.py [--redes efficientnet_b0]
"""
import argparse, csv, importlib.util, json, sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
REDES = ("resnet18", "efficientnet_b0", "densenet121")


def t12():
    spec = importlib.util.spec_from_file_location("treino12", RAIZ / "scripts" / "12_treinar.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dados", default="data/treino_ignis")
    ap.add_argument("--redes", nargs="+", default=list(REDES))
    ap.add_argument("--sufixo", default="torchvision")
    ap.add_argument("--split", default="test", choices=["test", "val"])
    a = ap.parse_args()
    import torch
    from PIL import Image
    T = t12(); pasta = RAIZ / a.dados
    if not (pasta / "split_manifest.csv").is_file():
        sys.exit(f"[PARADO] Não achei {pasta / 'split_manifest.csv'}. Rode antes a Etapa 11.")
    linhas = [l for l in csv.DictReader((pasta / "split_manifest.csv").open(encoding="utf-8")) if l["split"] == a.split]
    y = np.array([int(l["label"] == "Fire") for l in linhas])
    sai = RAIZ / "relatorios/15_robustez/cinza"; sai.mkdir(parents=True, exist_ok=True)
    _, aval = T.transformacoes(224, "nenhum")
    Xc, Xg = [], []
    for l in linhas:
        with Image.open(pasta / l["path"]) as im:
            im = im.convert("RGB"); Xc.append(aval(im)); Xg.append(aval(im.convert("L").convert("RGB")))
    Xc, Xg = torch.stack(Xc), torch.stack(Xg)

    f = lambda v: f"{100 * v:5.1f}%".replace(".", ",")
    res = [f"Etapa 15c | {datetime.now(timezone.utc).isoformat(timespec='seconds')} | teste em tons de cinza ({len(linhas)} imagens de {a.split})", "",
           f"  {'rede':<16} {'versão':<9} {'acurácia':>9} {'recall fogo':>12} {'especific.':>11}  VP/VN/FP/FN"]
    tab = []
    for rede in a.redes:
        nome = f"{rede}_{a.sufixo}"
        pesos = RAIZ / "data/modelos" / nome / "modelo.pth"; cfg = RAIZ / "relatorios/12_treino" / nome / "config.json"
        if not pesos.exists() or not cfg.exists(): print(f"[pulando] {nome}: faltam pesos ou config"); continue
        limiar = json.loads(cfg.read_text(encoding="utf-8"))["limiar_calibrado_na_validacao"]
        m = T.criar_rede(rede, pre_treinada=False); m.load_state_dict(torch.load(pesos, map_location="cpu")["estado"]); m.eval()
        with torch.no_grad():
            pr = lambda X: np.concatenate([torch.softmax(m(X[k:k + 32]), 1)[:, 1].numpy() for k in range(0, len(X), 32)])
            pc, pg = pr(Xc), pr(Xg)
        for versao, p in (("colorida", pc), ("cinza", pg)):
            mm = T.metricas(y, p, limiar); tab.append({"rede": rede, "versao": versao} | mm)
            res.append(f"  {rede:<16} {versao:<9} {f(mm['acuracia']):>9} {f(mm['recall_fogo']):>12} {f(mm['especificidade']):>11}"
                       f"  {mm['vp']}/{mm['vn']}/{mm['fp']}/{mm['fn']}")
        mudou = (pc >= limiar) != (pg >= limiar)
        perde = int(((pc >= limiar) & (pg < limiar) & (y == 1)).sum()); ganha = int(((pc < limiar) & (pg >= limiar) & (y == 0)).sum())
        res.append(f"  {'':<16} em cinza: {int(mudou.sum())} decisões mudam | fogo que deixa de ser visto: {perde} | novos alarmes falsos: {ganha}")
        with (sai / f"predicoes_{rede}.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh, lineterminator="\n"); w.writerow(["path", "classe_real", "prob_colorida", "prob_cinza", "mudou"])
            for k, l in enumerate(linhas):
                w.writerow([l["path"], l["label"], round(float(pc[k]), 4), round(float(pg[k]), 4), "sim" if mudou[k] else ""])
    if not tab: sys.exit("[ERRO] nenhuma rede da Etapa 12 encontrada.")
    res += ["", "Leitura: a queda do recall em cinza mede quanto a rede depende da cor. Queda grande + falso alarme no pôr do",
            "sol (14b) = a rede usa 'laranja' como atalho; o próximo treino deve trazer mais cenas laranja sem fogo."]
    with (sai / "metricas.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(tab[0]), lineterminator="\n"); w.writeheader(); w.writerows(tab)
    (sai / "resumo.txt").write_text("\n".join(res) + "\n", encoding="utf-8")
    print("\n".join(res)); print(f"\n[OK] {sai}")


if __name__ == "__main__":
    main()
