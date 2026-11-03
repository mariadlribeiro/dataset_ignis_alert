#!/usr/bin/env python3
"""
Etapa 5c - Lista para a SEGUNDA REVISÃO (só ambiente) das imagens que não passaram pela 1ª revisão.

Por quê: as imagens não revisadas ficariam com o ambiente sugerido pelo modelo. A auditoria cega
(amostra aleatória dessas mesmas imagens "seguras") mede quanto o modelo acerta em CADA ambiente que ele
sugere. Quando o pior caso do intervalo de confiança de 95% (Wilson) fica abaixo de --confianca-min,
a sugestão não é confiável e as imagens com essa sugestão entram nesta segunda revisão.

Entradas : relatorios/05_sugestoes/sugestoes.csv e revisao_preenchida.csv (1ª revisão, com a auditoria cega)
Saídas   : relatorios/05_sugestoes/
  revisao_ambiente.csv          -> mesmo formato do revisao.csv (a página 05b lê com --modo ambiente)
  revisao_ambiente_criterio.csv -> acerto do modelo por ambiente sugerido e a decisão de revisar ou não

Nada no dataset é alterado. Não sobrescreve revisao_ambiente.csv se já existir (use --forcar).

Uso:  python scripts/05c_revisao_ambiente.py [--confianca-min 0.80]
"""
import argparse, csv, math
from collections import Counter
from pathlib import Path


def ler(caminho):
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def gravar(caminho, linhas, cols):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(linhas)


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 1.0
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - m), min(1.0, c + m)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sugestoes", default="relatorios/05_sugestoes/sugestoes.csv")
    ap.add_argument("--revisao", default="relatorios/05_sugestoes/revisao_preenchida.csv")
    ap.add_argument("--saida", default="relatorios/05_sugestoes")
    ap.add_argument("--confianca-min", type=float, default=0.80,
                    help="revisa os ambientes cujo limite inferior do IC 95%% do acerto fica abaixo disto")
    ap.add_argument("--forcar", action="store_true", help="permite sobrescrever revisao_ambiente.csv")
    a = ap.parse_args()

    sug = ler(a.sugestoes)
    rev = ler(a.revisao)
    revisadas = {r["caminho_relativo"] for r in rev}
    aud = [r for r in rev if r["motivos_revisao"] == "auditoria" and r.get("ambiente_cego")]
    if not aud:
        raise SystemExit("Não há respostas cegas da auditoria em revisao_preenchida.csv (colunas *_cego).")

    nao_rev = [s for s in sug if s["caminho_relativo"] not in revisadas]
    pend_nao_rev = Counter(s["ambiente_sugerido"] for s in nao_rev)

    criterio, revisar = [], set()
    for amb in sorted(set(pend_nao_rev) | {r["ambiente_sugerido"] for r in aud}):
        casos = [r for r in aud if r["ambiente_sugerido"] == amb]
        k = sum(r["ambiente_cego"] == amb for r in casos); n = len(casos)
        lo, hi = wilson(k, n)
        decide = lo < a.confianca_min
        if decide:
            revisar.add(amb)
        criterio.append({"ambiente_sugerido": amb, "auditadas": n, "acertos": k,
                         "acerto": f"{k / n:.3f}" if n else "", "ic95_inf": f"{lo:.3f}", "ic95_sup": f"{hi:.3f}",
                         "nao_revisadas_com_esta_sugestao": pend_nao_rev.get(amb, 0),
                         "decisao": "revisar" if decide else "manter_sugestao"})

    lista = sorted((s for s in nao_rev if s["ambiente_sugerido"] in revisar),
                   key=lambda s: (s["ambiente_sugerido"], s["caminho_relativo"]))
    saida_rev = [{"n": n, "caminho_relativo": s["caminho_relativo"], "classe_original": s["classe_original"],
                  "motivos_revisao": "ambiente_nao_confiavel", "ambiente_sugerido": s["ambiente_sugerido"],
                  "fogo_sugerido": s["fogo_sugerido"], "fumaca_sugerida": s["fumaca_sugerida"],
                  "ambiente_confirmado": "", "fogo_confirmado": "", "fumaca_confirmada": "",
                  "camera_confirmada": "", "observacao": ""} for n, s in enumerate(lista, 1)]

    saida = Path(a.saida); saida.mkdir(parents=True, exist_ok=True)
    gravar(saida / "revisao_ambiente_criterio.csv", criterio, list(criterio[0].keys()))
    destino = saida / "revisao_ambiente.csv"
    if destino.exists() and not a.forcar:
        destino = saida / "revisao_ambiente_novo.csv"
        print(f"AVISO: revisao_ambiente.csv já existe e NÃO foi sobrescrito. Nova versão em {destino.name}")
    if saida_rev:
        gravar(destino, saida_rev, list(saida_rev[0].keys()))

    print(f"Auditoria cega usada: {len(aud)} imagens | critério: limite inferior do IC 95% < {a.confianca_min}")
    print(f"{'ambiente sugerido':18s} {'acerto':>12s} {'IC 95%':>14s} {'não revisadas':>14s}  decisão")
    for c in criterio:
        ac = f"{c['acertos']}/{c['auditadas']}"
        print(f"{c['ambiente_sugerido']:18s} {ac:>12s} {float(c['ic95_inf']):6.0%} a {float(c['ic95_sup']):4.0%}"
              f" {c['nao_revisadas_com_esta_sugestao']:>14d}  {c['decisao']}")
    print(f"\nImagens para a 2ª revisão (só ambiente): {len(saida_rev)} de {len(nao_rev)} não revisadas -> {destino}")
    print("Próximo passo: python scripts/05b_pagina_revisao.py --modo ambiente")
    print("Nada foi alterado no dataset.")


if __name__ == "__main__":
    main()
