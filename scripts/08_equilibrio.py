#!/usr/bin/env python3
"""
Etapa 8 - EQUILÍBRIO DO TREINO por PESO (SOMENTE LEITURA: nenhuma imagem é apagada, copiada ou duplicada).

Por quê: o treino tem cerca de 3 imagens com fogo para cada imagem sem fogo, e quase toda imagem urbana tem
fogo. Em vez de excluir imagens (o que perde informação) ou duplicá-las em disco, cada imagem do TREINO
recebe um peso. No treino, o sorteio de cada época usa esse peso (por exemplo, WeightedRandomSampler do
PyTorch), e assim o modelo vê as duas classes na mesma proporção.

Regras:
  * validação e teste NÃO recebem peso: eles medem o mundo real e ficam com a distribuição verdadeira;
  * imagens fora da divisão (sintéticas, sensor, GIF) não entram;
  * aumentação de dados (girar, recortar, brilho) acontece no treino, na memória, e nunca é salva.

Esquemas de peso:
  classe  (padrão) peso = N / (2 x n_da_classe). Cada classe (com fogo, sem fogo) vale metade do sorteio.
  estrato          Também equilibra os ambientes dentro de cada classe, com suavização (1 / raiz de n) e um
                   teto (--teto) para que um estrato com 1 ou 2 imagens não domine o treino.

Entrada : relatorios/06_plano/inventario.csv
Saídas  : relatorios/08_equilibrio/
  pesos_treino.csv  -> uma linha por imagem do treino: estrato, tamanho do estrato, peso e chance no sorteio
  diagnostico.csv   -> contagem por conjunto x ambiente x fogo, com as lacunas marcadas
  resumo.txt        -> o que muda no sorteio e as lacunas que só dados novos resolvem

Uso:  python scripts/08_equilibrio.py [--esquema classe|estrato] [--minimo 20] [--teto 5]
"""
import argparse, csv, math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

SPLITS = ("treino", "validacao", "teste")
ORDEM_AMB = ["floresta", "predios", "cidade", "casa", "flores_jardins", "outros", "ambiente_incerto"]


def ler(caminho):
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def gravar(caminho, linhas, cols):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(linhas)


def pesos_classe(treino):
    n = Counter(r["fogo"] for r in treino)
    return {id(r): len(treino) / (len(n) * n[r["fogo"]]) for r in treino}


def pesos_estrato(treino, teto):
    """Dentro de cada classe: peso proporcional a 1/raiz(n_estrato), com teto; depois cada classe soma N/2."""
    n_cls = Counter(r["fogo"] for r in treino)
    n_est = Counter((r["fogo"], r["ambiente"]) for r in treino)
    bruto = {id(r): 1 / math.sqrt(n_est[(r["fogo"], r["ambiente"])]) for r in treino}
    for c in n_cls:   # teto relativo ao menor peso da classe
        ids = [id(r) for r in treino if r["fogo"] == c]
        menor = min(bruto[i] for i in ids)
        for i in ids: bruto[i] = min(bruto[i], menor * teto)
    alvo = len(treino) / len(n_cls)
    soma = defaultdict(float)
    for r in treino: soma[r["fogo"]] += bruto[id(r)]
    return {id(r): bruto[id(r)] * alvo / soma[r["fogo"]] for r in treino}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventario", default="relatorios/06_plano/inventario.csv")
    ap.add_argument("--saida", default="relatorios/08_equilibrio")
    ap.add_argument("--esquema", choices=["classe", "estrato"], default="classe")
    ap.add_argument("--minimo", type=int, default=20, help="abaixo disso, o estrato é marcado como lacuna")
    ap.add_argument("--teto", type=float, default=5.0, help="(esquema estrato) peso máximo = teto x menor peso da classe")
    a = ap.parse_args()

    inv = ler(a.inventario)
    inc = [r for r in inv if r["situacao"] == "incluida"]
    erros = []
    if not inc: erros.append("nenhuma imagem incluída no inventário")
    for r in inc:
        if r["split"] not in SPLITS: erros.append(f"split inválido '{r['split']}' em {r['caminho_original']}")
        if r["fogo"] not in ("sim", "nao"): erros.append(f"fogo '{r['fogo']}' (precisa ser sim ou nao) em {r['caminho_original']}")
    if erros:
        raise SystemExit("Inventário inconsistente:\n  " + "\n  ".join(erros[:20]))

    treino = [r for r in inc if r["split"] == "treino"]
    w = pesos_classe(treino) if a.esquema == "classe" else pesos_estrato(treino, a.teto)
    total_w = sum(w.values())
    n_est = Counter((r["fogo"], r["ambiente"]) for r in treino)

    linhas = []
    for r in sorted(treino, key=lambda r: r["caminho_original"]):
        linhas.append({"caminho_original": r["caminho_original"], "nome_novo": r["nome_novo"], "destino": r["destino"],
                       "id_grupo": r["id_grupo"], "ambiente": r["ambiente"], "fogo": r["fogo"],
                       "estrato": f"{r['ambiente']}|{r['fogo']}", "n_estrato": n_est[(r["fogo"], r["ambiente"])],
                       "peso": f"{w[id(r)]:.6f}", "chance_sorteio": f"{w[id(r)] / total_w:.8f}"})
    saida = Path(a.saida); saida.mkdir(parents=True, exist_ok=True)
    gravar(saida / "pesos_treino.csv", linhas, list(linhas[0].keys()))

    # diagnóstico: conjunto x ambiente x fogo
    cont = Counter((r["split"], r["ambiente"], r["fogo"]) for r in inc)
    ambs = [x for x in ORDEM_AMB if any(k[1] == x for k in cont)] + sorted({k[1] for k in cont} - set(ORDEM_AMB))
    diag, lacunas = [], []
    for s in SPLITS:
        n_s = sum(v for k, v in cont.items() if k[0] == s)
        for amb in ambs:
            for f in ("sim", "nao"):
                q = cont[(s, amb, f)]
                lac = q < a.minimo
                diag.append({"conjunto": s, "ambiente": amb, "fogo": f, "imagens": q,
                             "pct_do_conjunto": f"{100 * q / n_s:.1f}", "lacuna": "sim" if lac else "nao"})
                if lac: lacunas.append((s, amb, f, q))
    gravar(saida / "diagnostico.csv", diag, list(diag[0].keys()))

    # o que muda no sorteio do treino
    antes = Counter(r["fogo"] for r in treino)
    depois = defaultdict(float)
    for r in treino: depois[r["fogo"]] += w[id(r)] / total_w
    est_antes = Counter(f"{r['ambiente']}|{r['fogo']}" for r in treino)
    est_depois = defaultdict(float)
    for r in treino: est_depois[f"{r['ambiente']}|{r['fogo']}"] += w[id(r)] / total_w
    pmin, pmax = min(w.values()), max(w.values())

    txt = [f"Etapa 8 gerada em {datetime.now(timezone.utc).isoformat(timespec='seconds')} | NENHUMA IMAGEM FOI ALTERADA",
           f"esquema: {a.esquema}" + (f" (teto {a.teto})" if a.esquema == "estrato" else ""),
           f"imagens incluídas: {len(inc)} | treino: {len(treino)} | validação e teste ficam sem peso (distribuição real)",
           "", "Treino, chance de cada classe no sorteio:"]
    for f, nome in (("sim", "com fogo"), ("nao", "sem fogo")):
        txt.append(f"  {nome:9s} antes {100 * antes[f] / len(treino):5.1f}%  ->  depois {100 * depois[f]:5.1f}%   ({antes[f]} imagens)")
    txt += [f"  peso mínimo {pmin:.3f} | máximo {pmax:.3f} | razão {pmax / pmin:.1f}x", "",
            "Treino por estrato (ambiente|fogo): imagens, chance antes -> depois"]
    for e in sorted(est_antes, key=lambda e: -est_antes[e]):
        txt.append(f"  {e:28s} {est_antes[e]:4d}   {100 * est_antes[e] / len(treino):5.1f}% -> {100 * est_depois[e]:5.1f}%")
    txt += ["", f"Lacunas (menos de {a.minimo} imagens no estrato). O peso NÃO resolve: faltam exemplos reais."]
    por_amb = defaultdict(list)
    for s, amb, f, q in lacunas: por_amb[(amb, f)].append(f"{s} {q}")
    for (amb, f), v in sorted(por_amb.items(), key=lambda kv: (kv[0][1] != "nao", kv[0][0])):
        txt.append(f"  {amb:16s} {'sem fogo' if f == 'nao' else 'com fogo'}: " + ", ".join(v))
    txt += ["", "Leitura: os estratos sem fogo fora da floresta são os que mais faltam. Sem eles o modelo pode",
            "aprender 'cena urbana = fogo', e o teste não mede alarmes falsos em cidade. Prioridade para os",
            "próximos datasets: cenas urbanas sem fogo e imagens que confundem (pôr do sol, luzes, neblina).",
            "", "Como usar no treino (PyTorch):",
            "  pesos = [float(l['peso']) for l in csv.DictReader(open('relatorios/08_equilibrio/pesos_treino.csv'))]",
            "  sampler = WeightedRandomSampler(pesos, num_samples=len(pesos), replacement=True)",
            "  (a ordem das imagens no Dataset do treino tem de ser a mesma do CSV)"]
    (saida / "resumo.txt").write_text("\n".join(txt) + "\n", encoding="utf-8")
    print("\n".join(txt))
    print(f"\nArquivos em {saida}. Nada no dataset foi alterado.")


if __name__ == "__main__":
    main()
