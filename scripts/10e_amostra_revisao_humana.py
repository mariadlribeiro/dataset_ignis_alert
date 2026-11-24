#!/usr/bin/env python3
"""
Etapa 10e - AMOSTRA para a revisão HUMANA das 400 imagens da 2ª fonte que entraram com rótulo da revisão por IA.

Por quê: na Etapa 10d, as 400 imagens novas entraram com rótulo dado pela revisão por IA (fonte_fogo = revisao_ia).
A avaliação de 24/11/2026 pediu para medir quanto esses rótulos mudam com olhos humanos e qual a concordância
(kappa) entre as revisoras e entre a revisão humana e a IA.

Desenho da amostra (sorteio com semente fixa; nada no dataset muda):
  * TODAS as imagens novas que estão no TESTE (58): o teste é usado uma única vez para medir as redes, então
    cada rótulo dele precisa ter passado por uma pessoa;
  * mais --resto imagens sorteadas entre as de treino e validação, estratificadas por ambiente|fogo
    (proporcional, com pelo menos 1 por estrato). Cada uma recebe um PESO = (imagens do estrato) / (sorteadas),
    usado na Etapa 10f para estimar o total das 400.
  * todas as linhas são CEGAS (motivo 'auditoria'): a revisora não vê pasta, caminho nem sugestão até responder,
    e a primeira resposta fica gravada em *_cego. O rótulo da IA nunca aparece na página.
  * com duas ou mais revisoras, cada uma recebe a mesma amostra em ORDEM PRÓPRIA (embaralhada pela semente + nome), com página,
    progresso salvo e CSV exportado separados, para que as duas revisões sejam independentes.

Saídas em relatorios/10_nova_fonte/<nome>/revisao_humana_A/:
  amostra.csv                    -> n, caminho, conjunto, estrato, peso e o rótulo da IA (só para a Etapa 10f)
  revisao_<revisora>.csv         -> lista no formato do 05b (sem o rótulo da IA)
  revisao_<revisora>.html        -> página de revisão (gerada pelo 05b_pagina_revisao.py)
  resumo.txt

Uso:
  python scripts/10e_amostra_revisao_humana.py                       (uma revisora; para duas: --revisoras nome1 nome2)
  python scripts/10e_amostra_revisao_humana.py --resto 60 --revisoras revisora --semente 42
Depois: cada revisora abre a sua página, revisa e exporta revisao_humana_<revisora>_preenchida.csv
para a mesma pasta; então rode scripts/10f_concordancia_revisao_humana.py.
"""
import argparse, csv, random, subprocess, sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

NOME = "cristiancristancho_forest-fire-image-dataset"


def ler(caminho):
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def gravar(caminho, linhas, cols):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(linhas)


def proporcional(contagem, total):
    """Divide 'total' entre os estratos proporcionalmente, com pelo menos 1 por estrato (maiores restos)."""
    n = sum(contagem.values())
    base = {k: max(1, int(total * v / n)) for k, v in contagem.items()}
    base = {k: min(base[k], contagem[k]) for k in base}
    resto = sorted(contagem, key=lambda k: -(total * contagem[k] / n - int(total * contagem[k] / n)))
    i = 0
    while sum(base.values()) < min(total, n):
        k = resto[i % len(resto)]
        if base[k] < contagem[k]: base[k] += 1
        i += 1
    return base


def main():
    ap = argparse.ArgumentParser()
    pasta = Path("relatorios/10_nova_fonte") / NOME
    ap.add_argument("--inventario", default=str(pasta / "integracao_A/inventario_novas.csv"))
    ap.add_argument("--selecao", default=str(pasta / "selecao_A"))
    ap.add_argument("--saida", default=str(pasta / "revisao_humana_A"))
    ap.add_argument("--origem", help="origem.json com caminho_local das imagens (padrão: o da seleção A)")
    ap.add_argument("--resto", type=int, default=60, help="quantas sortear entre treino e validação")
    ap.add_argument("--revisoras", nargs="+", default=["revisora"])
    ap.add_argument("--semente", type=int, default=42)
    ap.add_argument("--sem-pagina", action="store_true", help="só gera os CSVs, sem chamar o 05b")
    a = ap.parse_args()

    inv = [r for r in ler(a.inventario) if r["situacao"] == "incluida"]
    sel = Path(a.selecao)
    sug = {r["caminho_relativo"]: r for r in ler(sel / "sugestoes.csv")}
    nsel = {r["caminho_relativo"]: r["n"] for r in ler(sel / "revisao.csv")}
    rng = random.Random(a.semente)

    teste = [r for r in inv if r["split"] == "teste"]
    resto = [r for r in inv if r["split"] != "teste"]
    estr = lambda r: f"{r['ambiente']}|{r['fogo']}"
    por_estrato = defaultdict(list)
    for r in resto: por_estrato[estr(r)].append(r)
    cota = proporcional(Counter({k: len(v) for k, v in por_estrato.items()}), a.resto)

    amostra = []
    for r in teste:
        amostra.append(dict(r, parte="teste_completo", estrato=estr(r), peso="1"))
    for k in sorted(por_estrato):
        grupo = sorted(por_estrato[k], key=lambda r: r["caminho_original"])
        for r in rng.sample(grupo, cota[k]):
            amostra.append(dict(r, parte="sorteio_treino_validacao", estrato=k,
                                peso=f"{len(grupo) / cota[k]:.4f}"))
    amostra.sort(key=lambda r: int(nsel[r["caminho_original"]]))
    for r in amostra: r["n"] = nsel[r["caminho_original"]]     # mesmo número da revisão por IA (selecao_A)

    out = Path(a.saida); out.mkdir(parents=True, exist_ok=True)
    gravar(out / "amostra.csv", [dict(r, caminho_relativo=r["caminho_original"], ambiente_ia=r["ambiente"],
                                      fogo_ia=r["fogo"], fumaca_ia=r["fumaca"]) for r in amostra],
           ["n", "caminho_relativo", "split", "parte", "estrato", "peso", "ambiente_ia", "fogo_ia", "fumaca_ia", "sha256"])
    # sugestões do CLIP para a página (o rótulo da IA NÃO vai para cá)
    gravar(out / "sugestoes.csv", [sug[r["caminho_original"]] for r in amostra], list(next(iter(sug.values())).keys()))

    for rev in a.revisoras:
        ordem = amostra[:]; random.Random(f"{a.semente}-{rev}").shuffle(ordem)
        linhas = [{"n": r["n"], "caminho_relativo": r["caminho_original"], "classe_original": r["classe_original"],
                   "motivos_revisao": "auditoria"} for r in ordem]
        gravar(out / f"revisao_{rev}.csv", linhas, ["n", "caminho_relativo", "classe_original", "motivos_revisao",
               "ambiente_sugerido", "fogo_sugerido", "fumaca_sugerida", "ambiente_confirmado", "fogo_confirmado",
               "fumaca_confirmada", "camera_confirmada", "observacao"])
        if not a.sem_pagina:
            subprocess.run([sys.executable, str(Path(__file__).with_name("05b_pagina_revisao.py")),
                            "--origem", a.origem or str(sel / "origem.json"),
                            "--revisao", str(out / f"revisao_{rev}.csv"), "--sugestoes", str(out / "sugestoes.csv"),
                            "--saida", str(out / f"revisao_{rev}.html"),
                            "--exportar-como", f"revisao_humana_{rev}_preenchida.csv",
                            "--chave", f"ignis_revisao_humana_A_{rev}"], check=True)

    c = Counter((r["parte"], r["estrato"]) for r in amostra)
    txt = [f"Etapa 10e gerada em {datetime.now(timezone.utc).isoformat(timespec='seconds')} | semente {a.semente}",
           f"imagens novas com rótulo da IA: {len(inv)} | na amostra: {len(amostra)}",
           f"  teste (todas): {len(teste)} | treino e validação sorteadas: {len(amostra) - len(teste)} de {len(resto)}",
           "", "amostra por parte e estrato (peso = imagens do estrato / sorteadas):"]
    for (p, k), v in sorted(c.items()):
        peso = next(r["peso"] for r in amostra if r["parte"] == p and r["estrato"] == k)
        txt.append(f"  {p:<26} {k:<16} {v:>4}   peso {float(peso):.2f}")
    txt += ["", "revisoras: " + ", ".join(a.revisoras) + (" (mesma amostra, ordens diferentes, revisões independentes)" if len(a.revisoras) > 1 else " (revisão única)"),
            "todas as linhas são cegas; o rótulo da IA fica só em amostra.csv."]
    (out / "resumo.txt").write_text("\n".join(txt) + "\n", encoding="utf-8")
    print("\n".join(txt))


if __name__ == "__main__":
    main()
