#!/usr/bin/env python3
"""
Etapa 10h - REVISÃO HUMANA CEGA das imagens novas que a IA chamou de ambiente "outros" e ficaram fora da amostra (10e).

Por quê: no desempate (10g), 27 das 29 fotos "outros" da amostra eram floresta ou cidade. Em vez de estimar, as
restantes (66, todas de treino e validação) passam por uma pessoa, e a contagem da floresta fica exata.

Mesmo protocolo da 10e: todas as linhas cegas (motivo 'auditoria'), ordem embaralhada pela semente, o rótulo da IA
fica só em outros.csv. Depois de exportar, rode a 10f nesta pasta:
  python scripts/10h_revisao_outros.py
  (revisar e exportar revisao_humana_revisora_preenchida.csv para revisao_humana_A/outros/)
  python scripts/10f_concordancia_revisao_humana.py --pasta relatorios/10_nova_fonte/cristiancristancho_forest-fire-image-dataset/revisao_humana_A/outros
"""
import argparse, csv, random, subprocess, sys
from pathlib import Path

NOME = "cristiancristancho_forest-fire-image-dataset"


def ler(caminho):
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def gravar(caminho, linhas, cols):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(linhas)


def main():
    pasta = Path("relatorios/10_nova_fonte") / NOME
    ap = argparse.ArgumentParser()
    ap.add_argument("--revisora", default="revisora")
    ap.add_argument("--semente", type=int, default=42)
    a = ap.parse_args()
    sel, hum = pasta / "selecao_A", pasta / "revisao_humana_A"
    out = hum / "outros"; out.mkdir(parents=True, exist_ok=True)

    inv = [r for r in ler(pasta / "integracao_A/inventario_novas.csv") if r["situacao"] == "incluida"]
    ja = {r["caminho_relativo"] for r in ler(hum / "amostra.csv")}
    nsel = {r["caminho_relativo"]: r["n"] for r in ler(sel / "revisao.csv")}
    sug = {r["caminho_relativo"]: r for r in ler(sel / "sugestoes.csv")}
    alvo = sorted((r for r in inv if r["ambiente"] == "outros" and r["caminho_original"] not in ja),
                  key=lambda r: int(nsel[r["caminho_original"]]))

    # 'amostra.csv' com peso 1: é a população inteira que faltava, então a 10f conta direto
    gravar(out / "amostra.csv", [dict(r, n=nsel[r["caminho_original"]], caminho_relativo=r["caminho_original"],
                                      parte="outros_restantes", estrato=f"{r['ambiente']}|{r['fogo']}", peso="1",
                                      ambiente_ia=r["ambiente"], fogo_ia=r["fogo"], fumaca_ia=r["fumaca"]) for r in alvo],
           ["n", "caminho_relativo", "split", "parte", "estrato", "peso", "ambiente_ia", "fogo_ia", "fumaca_ia", "sha256"])
    gravar(out / "sugestoes.csv", [sug[r["caminho_original"]] for r in alvo], list(next(iter(sug.values())).keys()))
    ordem = alvo[:]; random.Random(f"{a.semente}-outros-{a.revisora}").shuffle(ordem)
    gravar(out / f"revisao_{a.revisora}.csv",
           [{"n": nsel[r["caminho_original"]], "caminho_relativo": r["caminho_original"], "classe_original": r["classe_original"],
             "motivos_revisao": "auditoria"} for r in ordem],
           ["n", "caminho_relativo", "classe_original", "motivos_revisao", "ambiente_sugerido", "fogo_sugerido",
            "fumaca_sugerida", "ambiente_confirmado", "fogo_confirmado", "fumaca_confirmada", "camera_confirmada", "observacao"])
    subprocess.run([sys.executable, str(Path(__file__).with_name("05b_pagina_revisao.py")),
                    "--origem", str(sel / "origem.json"), "--revisao", str(out / f"revisao_{a.revisora}.csv"),
                    "--sugestoes", str(out / "sugestoes.csv"), "--saida", str(out / f"revisao_{a.revisora}.html"),
                    "--exportar-como", f"revisao_humana_{a.revisora}_preenchida.csv",
                    "--chave", f"ignis_revisao_outros_A_{a.revisora}"], check=True)
    print(f"{len(alvo)} imagens 'outros' fora da amostra -> {out}")


if __name__ == "__main__":
    main()
