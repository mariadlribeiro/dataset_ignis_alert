#!/usr/bin/env python3
"""
Etapa 10f - CONCORDÂNCIA da revisão humana (10e) com a revisão por IA e entre as revisoras (SOMENTE LEITURA).

Lê revisao_humana_A/amostra.csv e os CSVs exportados pelas páginas (revisao_humana_<revisora>_preenchida.csv).
Usa só a PRIMEIRA resposta cega de cada imagem (colunas *_cego), que foi dada sem ver sugestão nenhuma.

Mede, para ambiente, fogo e fumaça:
  * revisora x IA: concordância, intervalo de 95% (Wilson) e kappa de Cohen;
  * revisora x revisora: concordância e kappa (só se houver duas revisões; com uma, esta parte é pulada);
  * quantos rótulos mudam: no teste (contagem exata, todas as 58 estão na amostra) e estimativa para as 400
    (soma dos pesos da amostra), com intervalo aproximado.
Atenção: quase todas as 400 são "sem fogo"; com uma classe tão rara, o kappa pode sair baixo ou indefinido mesmo
com concordância alta (paradoxo da prevalência). Por isso os dois números são reportados.

Saídas em revisao_humana_A/:
  concordancia.txt   -> o relatório
  divergencias.csv   -> imagens em que alguém discorda (revisora x IA ou revisora x revisora), para desempate
Nada no dataset muda: corrigir rótulos é decisão humana, registrada depois em selecao_A/decisoes.csv.

Uso:  python scripts/10f_concordancia_revisao_humana.py [--revisoras revisora]
"""
import argparse, csv, math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

NOME = "cristiancristancho_forest-fire-image-dataset"
CAMPOS = ["ambiente", "fogo", "fumaca"]


def ler(caminho):
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def wilson(k, n, z=1.96):
    if n == 0: return (float("nan"),) * 2
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - m), min(1.0, c + m)


def kappa(a, b):
    n = len(a)
    if n == 0: return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return float("nan") if pe == 1 else (po - pe) / (1 - pe)


def pct(x): return "—" if x != x else f"{100 * x:.1f}%".replace(".", ",")
def num(x): return "indefinido" if x != x else f"{x:.2f}".replace(".", ",")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pasta", default=str(Path("relatorios/10_nova_fonte") / NOME / "revisao_humana_A"))
    ap.add_argument("--revisoras", nargs="+", default=["revisora"])
    a = ap.parse_args()
    pasta = Path(a.pasta)
    amostra = {r["caminho_relativo"]: r for r in ler(pasta / "amostra.csv")}

    resp = {}
    for rev in a.revisoras:
        f = pasta / f"revisao_humana_{rev}_preenchida.csv"
        if not f.exists():
            print(f"(sem {f.name}: revisão de {rev} ainda não exportada)"); continue
        resp[rev] = {r["caminho_relativo"]: {c: r[f"{c}_cego"] for c in CAMPOS}
                     for r in ler(f) if all(r.get(f"{c}_cego") for c in CAMPOS)}
    if not resp: raise SystemExit("Nenhuma revisão exportada ainda. Exporte o CSV de cada página para " + str(pasta))

    L = [f"Etapa 10f gerada em {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
         f"imagens revisadas: {len(amostra)} ({', '.join(f'{p}: {n}' for p, n in Counter(r['parte'] for r in amostra.values()).items())})", ""]
    for rev, d in resp.items():
        ch = [c for c in amostra if c in d]
        L += [f"== {rev}: {len(ch)} de {len(amostra)} imagens com resposta cega completa", "",
              f"  {'campo':<9} {'concorda c/ IA':>15} {'IC 95% (Wilson)':>18} {'kappa':>11}"]
        for c in CAMPOS:
            x = [d[k][c] for k in ch]; y = [amostra[k][f"{c}_ia"] for k in ch]
            k = sum(i == j for i, j in zip(x, y)); lo, hi = wilson(k, len(ch))
            L.append(f"  {c:<9} {k:>4} de {len(ch):<4} {pct(k / len(ch)) if ch else '—':>6}   {pct(lo):>6} a {pct(hi):<6} {num(kappa(x, y)):>11}")
        # rótulo de FOGO que muda: no teste (exato) e estimado para as 400
        muda = [k for k in ch if d[k]["fogo"] != amostra[k]["fogo_ia"]]
        teste = [k for k in ch if amostra[k]["parte"] == "teste_completo"]
        muda_t = [k for k in muda if k in teste]
        est = sum(float(amostra[k]["peso"]) for k in muda)
        peso_tot = sum(float(amostra[k]["peso"]) for k in ch)
        p = est / peso_tot if peso_tot else float("nan"); lo, hi = wilson(len(muda), len(ch))
        L += ["", f"  fogo diferente da IA: {len(muda)} na amostra | no teste: {len(muda_t)} de {len(teste)}"]
        if any(amostra[k]["parte"].startswith("sorteio") for k in ch):
            L.append(f"  estimativa para as 400: {p * 400:.0f} rótulos de fogo mudariam ({pct(p)}; "
                     f"faixa aproximada {lo * 400:.0f} a {hi * 400:.0f}, sem peso)")
        L.append("")
        trocas = Counter((amostra[k]["fogo_ia"], d[k]["fogo"]) for k in muda)
        for (de, para), v in trocas.most_common():
            L.append(f"    IA '{de}' -> {rev} '{para}': {v}")
        L.append("")

    if len(resp) >= 2:
        (r1, d1), (r2, d2) = list(resp.items())[:2]
        ch = [c for c in amostra if c in d1 and c in d2]
        L += [f"== {r1} x {r2}: {len(ch)} imagens respondidas pelas duas", "",
              f"  {'campo':<9} {'concordância':>15} {'IC 95% (Wilson)':>18} {'kappa':>11}"]
        for c in CAMPOS:
            x = [d1[k][c] for k in ch]; y = [d2[k][c] for k in ch]
            k = sum(i == j for i, j in zip(x, y)); lo, hi = wilson(k, len(ch))
            L.append(f"  {c:<9} {k:>4} de {len(ch):<4} {pct(k / len(ch)) if ch else '—':>6}   {pct(lo):>6} a {pct(hi):<6} {num(kappa(x, y)):>11}")
        L.append("")

    div = []
    for k, r in sorted(amostra.items(), key=lambda kv: int(kv[1]["n"])):
        lin = {"n": r["n"], "caminho_relativo": k, "split": r["split"], **{f"{c}_ia": r[f"{c}_ia"] for c in CAMPOS}}
        valores = {}
        for rev, d in resp.items():
            for c in CAMPOS:
                lin[f"{c}_{rev}"] = d.get(k, {}).get(c, "")
                if lin[f"{c}_{rev}"]: valores.setdefault(c, set()).update({lin[f"{c}_{rev}"], r[f"{c}_ia"]})
        motivos = [c for c, v in valores.items() if len(v) > 1]
        if motivos:
            lin["diverge_em"] = "+".join(motivos); lin["decisao_final"] = ""; div.append(lin)
    cols = ["n", "caminho_relativo", "split", "diverge_em"] + [f"{c}_ia" for c in CAMPOS] + \
           [f"{c}_{rev}" for rev in resp for c in CAMPOS] + ["decisao_final"]
    with open(pasta / "divergencias.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(div)
    L += [f"divergências para desempate: {len(div)} imagens (divergencias.csv)",
          "kappa baixo com concordância alta é esperado quando quase tudo é de uma classe só."]
    (pasta / "concordancia.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
