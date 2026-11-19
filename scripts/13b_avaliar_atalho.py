#!/usr/bin/env python3
"""
Etapa 13b - AVALIAR O TESTE DE ATALHO (nenhuma imagem é alterada; nada é treinado).

Lê a revisão cega da Etapa 13a (CSV exportado pela página), passa cada imagem pelas redes já treinadas na
Etapa 12 (com o MESMO limiar calibrado na validação) e compara com o teste principal.

Como ler:
  * no teste de atalho, TODAS as imagens têm o formato que no treino só aparecia sem fogo;
  * se o recall de fogo aqui ficar perto do teste principal, a rede acha a chama mesmo nesse formato;
  * se cair muito (ex.: diz "sem fogo" para fogo quadrado e pequeno), ela aprendeu o formato: é atalho.

Rótulos: fogo_confirmado da revisão (sim = chama visível; nao = sem chama, mesmo com fumaça).
Ficam de fora (listadas com motivo): imagens sem revisão, fogo "incerto" e o que não for fotografia.

Entradas: relatorios/13_atalho/origem.json, o CSV preenchido da revisão,
          data/modelos/<rede>_torchvision/modelo.pth e relatorios/12_treino/<rede>_torchvision/
Saídas  : relatorios/13_atalho/resultado/ (resumo.txt, metricas.csv, predicoes_<rede>.csv, fora.csv)

Uso:
  python scripts/13b_avaliar_atalho.py --revisao relatorios\\13_atalho\\revisao_atalho_preenchida.csv
"""
import argparse, csv, importlib.util, json, sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from PIL import Image

RAIZ = Path(__file__).resolve().parent.parent
REDES = ("resnet18", "efficientnet_b0", "densenet121")

_spec = importlib.util.spec_from_file_location("treino12", RAIZ / "scripts" / "12_treinar.py")
t12 = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(t12)


def ler(c):
    with open(c, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--revisao", required=True, help="CSV exportado pela página de revisão do teste de atalho")
    ap.add_argument("--pasta", default="relatorios/13_atalho")
    ap.add_argument("--redes", nargs="+", default=list(REDES))
    ap.add_argument("--sufixo", default="torchvision", help="nome das execuções da Etapa 12: <rede>_<sufixo>")
    a = ap.parse_args()

    pasta = RAIZ / a.pasta; sai = pasta / "resultado"; sai.mkdir(parents=True, exist_ok=True)
    raiz_fonte = Path(json.loads((pasta / "origem.json").read_text(encoding="utf-8"))["caminho_local"])
    rev = ler(a.revisao)
    sel = {r["caminho_relativo"]: r for r in ler(pasta / "revisao.csv")}

    itens, fora = [], []
    for r in rev:
        cam = r["caminho_relativo"]
        if cam not in sel:
            fora.append((cam, "não faz parte da seleção da Etapa 13a")); continue
        f, tipo = r.get("fogo_confirmado", ""), r.get("tipo_imagem", "fotografia") or "fotografia"
        if r.get("revisado") == "nao" or not f:
            fora.append((cam, "sem revisão")); continue
        if tipo != "fotografia":
            fora.append((cam, f"não é fotografia ({tipo})")); continue
        if f not in ("sim", "nao"):
            fora.append((cam, f"fogo {f}")); continue
        itens.append({"cam": cam, "y": int(f == "sim"), "sug": sel[cam]["fogo_sugerido"],
                      "fumaca": r.get("fumaca_confirmada", ""), "obs": r.get("observacao", "")})
    if not itens:
        sys.exit("[ERRO] nenhuma imagem revisada com fogo sim/nao no CSV.")
    n_fogo = sum(i["y"] for i in itens); n_sem = len(itens) - n_fogo
    concord = sum((i["sug"] == "sim") == bool(i["y"]) for i in itens) / len(itens)
    print(f"Teste de atalho: {len(itens)} imagens (com fogo {n_fogo}, sem fogo {n_sem}) | fora: {len(fora)}")

    _, aval = t12.transformacoes(224, "nenhum")
    X = []
    for i in itens:
        with Image.open(raiz_fonte / Path(*i["cam"].replace("\\", "/").split("/"))) as im:
            X.append(aval(im.convert("RGB")))
    X = torch.stack(X)
    y = np.array([i["y"] for i in itens])

    linhas, txt = [], []
    for rede in a.redes:
        nome = f"{rede}_{a.sufixo}"
        pesos = RAIZ / "data/modelos" / nome / "modelo.pth"
        cfg_p = RAIZ / "relatorios/12_treino" / nome / "config.json"
        if not pesos.exists() or not cfg_p.exists():
            print(f"[pulando] {nome}: faltam pesos ou config da Etapa 12"); continue
        cfg = json.loads(cfg_p.read_text(encoding="utf-8")); limiar = cfg["limiar_calibrado_na_validacao"]
        m = t12.criar_rede(rede, pre_treinada=False)
        m.load_state_dict(torch.load(pesos, map_location="cpu")["estado"]); m.eval()
        with torch.no_grad():
            p = np.concatenate([torch.softmax(m(X[k:k + 32]), 1)[:, 1].numpy() for k in range(0, len(X), 32)])
        at = t12.metricas(y, p, limiar); at["auc_roc"] = t12.auc_roc(y, p)
        tp = json.loads((RAIZ / "relatorios/12_treino" / nome / "metricas_teste.json").read_text(encoding="utf-8"))
        linhas.append({"rede": rede, "limiar": limiar,
                       "recall_fogo_teste": round(tp["recall_fogo"], 4), "recall_fogo_atalho": round(at["recall_fogo"], 4),
                       "especificidade_teste": round(tp["especificidade"], 4), "especificidade_atalho": round(at["especificidade"], 4),
                       "f2_teste": round(tp["f2_fogo"], 4), "f2_atalho": round(at["f2_fogo"], 4),
                       "auc_atalho": round(at["auc_roc"], 4), "fn_atalho": at["fn"], "fp_atalho": at["fp"],
                       "imagens_atalho": len(y)})
        with (sai / f"predicoes_{rede}.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(["caminho_relativo", "classe_revisada", "prob_fogo", "previsto", "erro", "fumaca", "observacao"])
            for i, pp in zip(itens, p):
                prev = int(pp >= limiar)
                erro = "" if prev == i["y"] else ("falso_negativo" if i["y"] else "falso_positivo")
                w.writerow([i["cam"], "Fire" if i["y"] else "NoFire", round(float(pp), 4), "Fire" if prev else "NoFire", erro, i["fumaca"], i["obs"]])
        queda = tp["recall_fogo"] - at["recall_fogo"]
        leitura = ("SINAL DE ATALHO: perde muito mais fogo no formato da segunda fonte" if queda > 0.15 else
                   "atenção: alguma perda de fogo no formato da segunda fonte" if queda > 0.05 else
                   "sem sinal de atalho de formato: acha o fogo também nesse formato")
        txt.append(f"  {rede:16s} recall de fogo {tp['recall_fogo']:.3f} -> {at['recall_fogo']:.3f} | "
                   f"especificidade {tp['especificidade']:.3f} -> {at['especificidade']:.3f} | "
                   f"FN {at['fn']} FP {at['fp']} | {leitura}")

    if not linhas:
        sys.exit("[ERRO] nenhuma rede da Etapa 12 encontrada.")
    with (sai / "metricas.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0])); w.writeheader(); w.writerows(linhas)
    with (sai / "fora.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["caminho_relativo", "motivo"]); w.writerows(fora)
    res = [f"Etapa 13b | {datetime.now(timezone.utc).isoformat(timespec='seconds')} | teste de atalho (só avaliação)",
           f"{len(itens)} imagens da segunda fonte, todas de floresta, quadradas e pequenas: "
           f"com fogo {n_fogo}, sem fogo {n_sem} (rótulo da revisão cega) | fora: {len(fora)} (fora.csv)",
           f"A sugestão do CLIP concordou com a revisão em {concord:.0%} das imagens.", "",
           "Teste principal -> teste de atalho (mesmo limiar da validação):"] + txt + [
           "", "Leitura: o recall de fogo é o número que responde à pergunta. Uma queda grande quer dizer que a rede",
           "usa o formato da imagem (quadrada e pequena = sem fogo) em vez de olhar a chama."]
    (sai / "resumo.txt").write_text("\n".join(res) + "\n", encoding="utf-8")
    print("\n".join(res)); print(f"\n[OK] Resultados em {sai}")


if __name__ == "__main__":
    main()
