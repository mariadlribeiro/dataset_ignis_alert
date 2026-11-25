#!/usr/bin/env python3
"""
Etapa 14b - AVALIAR OS NEGATIVOS DIFÍCEIS (nenhuma imagem é alterada; nada é treinado).

Lê a revisão cega da Etapa 14a, passa cada imagem pelas redes da Etapa 12 (com o MESMO limiar calibrado na
validação) e mede a TAXA DE FALSO ALARME só nas cenas difíceis, por tipo de cena, com intervalo de 95% (Wilson).

Entram como negativo difícil: imagens revisadas com fogo "nao" e cena de um dos seis tipos difíceis.
Ficam como CONTROLE: fogo "nao" e cena "nenhuma" (cena comum, da mesma fonte e do mesmo período).
Ficam de fora (fora.csv): sem revisão, fogo "sim" (o CLIP trouxe um incêndio) ou "incerto".

Comparação: taxa de falso alarme no teste principal (1 - especificidade, da Etapa 12) x controle x difíceis.

Entradas: relatorios/14_negativos/ (origem.json, candidatos.csv), o CSV preenchido da revisão,
          data/modelos/<rede>_torchvision/modelo.pth e relatorios/12_treino/<rede>_torchvision/
Saídas  : relatorios/14_negativos/resultado/ (resumo.txt, metricas.csv, predicoes_<rede>.csv, fora.csv)

Uso:
  python scripts/14b_avaliar_negativos.py --revisao relatorios\\14_negativos\\revisao_negativos_preenchida.csv
"""
import argparse, csv, importlib.util, json, math, sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
REDES = ("resnet18", "efficientnet_b0", "densenet121")
TIPOS = {"por_do_sol": "Pôr ou nascer do sol", "neblina": "Neblina ou névoa", "nuvens": "Nuvens", "outono": "Folhagem de outono",
         "luzes_noite": "Luzes à noite", "reflexo_brilho": "Reflexo ou brilho de sol"}


def ler(c):
    with open(c, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def wilson(k, n, z=1.96):
    if n == 0: return float("nan"), float("nan")
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - m), min(1.0, c + m)


def taxa(k, n):
    if n == 0: return "      —"
    lo, hi = wilson(k, n)
    return f"{k:>3}/{n:<3} {100 * k / n:5.1f}% ({100 * lo:4.1f} a {100 * hi:4.1f})".replace(".", ",")


def probabilidades(itens, raiz_fonte, redes, sufixo, falso=False):
    """prob. de fogo de cada imagem em cada rede, e o limiar de cada rede."""
    if falso:   # SÓ PARA TESTAR O SCRIPT
        rng = np.random.default_rng(0)
        return {r: (rng.random(len(itens)) ** 3, 0.5, {"especificidade": 0.99, "fp": 1, "vn": 94}) for r in redes}
    import torch
    from PIL import Image
    spec = importlib.util.spec_from_file_location("treino12", RAIZ / "scripts" / "12_treinar.py")
    t12 = importlib.util.module_from_spec(spec); spec.loader.exec_module(t12)
    _, aval = t12.transformacoes(224, "nenhum")
    X = []
    for i in itens:
        with Image.open(raiz_fonte / Path(*i["cam"].replace("\\", "/").split("/"))) as im:
            X.append(aval(im.convert("RGB")))
    X = torch.stack(X); saida = {}
    for rede in redes:
        nome = f"{rede}_{sufixo}"
        pesos = RAIZ / "data/modelos" / nome / "modelo.pth"; cfg_p = RAIZ / "relatorios/12_treino" / nome / "config.json"
        if not pesos.exists() or not cfg_p.exists():
            print(f"[pulando] {nome}: faltam pesos ou config da Etapa 12"); continue
        limiar = json.loads(cfg_p.read_text(encoding="utf-8"))["limiar_calibrado_na_validacao"]
        m = t12.criar_rede(rede, pre_treinada=False)
        m.load_state_dict(torch.load(pesos, map_location="cpu")["estado"]); m.eval()
        with torch.no_grad():
            p = np.concatenate([torch.softmax(m(X[k:k + 32]), 1)[:, 1].numpy() for k in range(0, len(X), 32)])
        tp = json.loads((RAIZ / "relatorios/12_treino" / nome / "metricas_teste.json").read_text(encoding="utf-8"))
        saida[rede] = (p, limiar, tp)
    return saida


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--revisao", required=True, help="CSV exportado pela página da Etapa 14a")
    ap.add_argument("--pasta", default="relatorios/14_negativos")
    ap.add_argument("--redes", nargs="+", default=list(REDES))
    ap.add_argument("--sufixo", default="torchvision")
    ap.add_argument("--teste-sem-modelo", action="store_true", help="probabilidades aleatórias, só para testar o script")
    a = ap.parse_args()

    pasta = RAIZ / a.pasta; sai = pasta / "resultado"; sai.mkdir(parents=True, exist_ok=True)
    if not Path(a.revisao).is_file():
        sys.exit(f"[PARADO] Não achei {a.revisao}. Exporte a revisão da página relatorios\\14_negativos\\revisao_negativos.html.")
    raiz_fonte = Path(json.loads((pasta / "origem.json").read_text(encoding="utf-8"))["caminho_local"])
    cand = {r["caminho_relativo"]: r for r in ler(pasta / "candidatos.csv")}

    itens, fora = [], []
    for r in ler(a.revisao):
        cam = r["caminho_relativo"]
        if cam not in cand: fora.append((cam, "não faz parte da seleção da 14a")); continue
        if r.get("revisado") != "sim": fora.append((cam, "sem revisão")); continue
        if r["fogo"] != "nao": fora.append((cam, f"fogo {r['fogo']} na revisão")); continue
        grupo = "dificil" if r["cena"] in TIPOS else "controle"
        itens.append({"cam": cam, "cena": r["cena"], "grupo": grupo, "fumaca": r["fumaca"],
                      "tipo_sugerido": cand[cam]["tipo_sugerido"], "obs": r.get("observacao", "")})
    if not itens: sys.exit("[ERRO] nenhuma imagem revisada com fogo 'nao' no CSV.")
    dif = [i for i in itens if i["grupo"] == "dificil"]; ctl = [i for i in itens if i["grupo"] == "controle"]
    acerto_clip = sum(i["cena"] == i["tipo_sugerido"] for i in itens) / len(itens)
    print(f"Negativos difíceis: {len(dif)} | controle (cena comum): {len(ctl)} | fora: {len(fora)}")

    probs = probabilidades(itens, raiz_fonte, a.redes, a.sufixo, a.teste_sem_modelo)
    if not probs: sys.exit("[ERRO] nenhuma rede da Etapa 12 encontrada.")

    linhas, txt, soma = [], [], defaultdict(float)
    for rede, (p, limiar, tp) in probs.items():
        alarme = p >= limiar
        for k, i in enumerate(itens): soma[i["cam"]] += float(p[k]) / len(probs)
        fp_t = tp.get("fp"); n_t = (tp.get("fp") or 0) + (tp.get("vn") or 0)
        kd = sum(bool(alarme[k]) for k, i in enumerate(itens) if i["grupo"] == "dificil")
        kc = sum(bool(alarme[k]) for k, i in enumerate(itens) if i["grupo"] == "controle")
        txt += ["", f"{rede} (limiar {limiar:.3f})",
                f"  {'teste principal (sem fogo)':<30} {taxa(fp_t, n_t) if fp_t is not None else '—'}",
                f"  {'controle: cena comum':<30} {taxa(kc, len(ctl))}",
                f"  {'NEGATIVOS DIFÍCEIS (todos)':<30} {taxa(kd, len(dif))}"]
        lin = {"rede": rede, "limiar": round(limiar, 4), "fa_teste_principal": round(1 - tp["especificidade"], 4),
               "fa_controle": round(kc / len(ctl), 4) if ctl else "", "fa_dificeis": round(kd / len(dif), 4) if dif else "",
               "alarmes_dificeis": kd, "imagens_dificeis": len(dif)}
        for t, nome in TIPOS.items():
            idx = [k for k, i in enumerate(itens) if i["cena"] == t]
            kt = sum(bool(alarme[k]) for k in idx)
            txt.append(f"    {nome:<28} {taxa(kt, len(idx))}")
            lin[f"fa_{t}"] = round(kt / len(idx), 4) if idx else ""; lin[f"n_{t}"] = len(idx)
        linhas.append(lin)
        with (sai / f"predicoes_{rede}.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(["caminho_relativo", "grupo", "cena", "fumaca", "prob_fogo", "alarme_falso", "observacao"])
            for k, i in enumerate(itens):
                w.writerow([i["cam"], i["grupo"], i["cena"], i["fumaca"], round(float(p[k]), 4), "sim" if alarme[k] else "", i["obs"]])

    with (sai / "metricas.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0])); w.writeheader(); w.writerows(linhas)
    with (sai / "fora.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["caminho_relativo", "motivo"]); w.writerows(fora)

    piores = sorted(dif, key=lambda i: -soma[i["cam"]])[:10]
    cnt = Counter(i["cena"] for i in dif)
    res = [f"Etapa 14b | {datetime.now(timezone.utc).isoformat(timespec='seconds')} | negativos difíceis (só avaliação)"
           + (" | TESTE SEM MODELO: números falsos" if a.teste_sem_modelo else ""),
           f"{len(dif)} negativos difíceis + {len(ctl)} de controle, todos sem fogo pela revisão cega | fora: {len(fora)} (fora.csv)",
           "  por cena: " + ", ".join(f"{TIPOS[t]} {cnt[t]}" for t in TIPOS),
           f"O tipo de cena sugerido pelo CLIP bateu com a revisão em {acerto_clip:.0%} das imagens.", "",
           "Taxa de FALSO ALARME (alarmes / imagens sem fogo, intervalo de 95% de Wilson), mesmo limiar da validação:"]
    res += txt + ["", "Imagens que mais enganam (média da prob. de fogo nas redes):"]
    res += [f"  {soma[i['cam']]:.2f}  {TIPOS[i['cena']]:<26} {i['cam']}" for i in piores]
    res += ["", "Leitura: se a taxa nos difíceis for muito maior que no teste principal, o teste principal subestima os",
            "alarmes falsos do uso real. O tipo de cena com a maior taxa é o primeiro a reforçar no treino."]
    (sai / "resumo.txt").write_text("\n".join(res) + "\n", encoding="utf-8")
    print("\n".join(res)); print(f"\n[OK] Resultados em {sai}")


if __name__ == "__main__":
    main()
