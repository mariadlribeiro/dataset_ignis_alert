#!/usr/bin/env python3
"""
Etapa 10j - REVISÃO HUMANA CEGA das imagens novas que ainda têm só o rótulo da IA (216, treino e validação).

Por quê: depois da 10e (amostra) e da 10h ("outros"), 216 imagens da 2ª fonte seguem com fonte_* = revisao_ia.
Com esta etapa, toda imagem da 2ª fonte passa por uma pessoa e nenhum número do site depende de estimativa.

Mesmo protocolo da 10e: todas as linhas cegas (motivo 'auditoria'), ordem embaralhada pela semente, o rótulo da IA
fica só em outros.csv. Depois de exportar, rode a 10f nesta pasta:
  python scripts/10j_revisao_restantes.py
  (revisar e exportar revisao_humana_revisora_preenchida.csv para revisao_humana_A/restantes/)
  python scripts/10f_concordancia_revisao_humana.py --pasta relatorios/10_nova_fonte/cristiancristancho_forest-fire-image-dataset/revisao_humana_A/restantes
  python scripts/10i_aplicar_rotulos_humanos.py --mover
  python scripts/11_exportar_treino.py
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
    out = hum / "restantes"; out.mkdir(parents=True, exist_ok=True)

    inv = [r for r in ler(pasta / "integracao_A/inventario_novas.csv") if r["situacao"] == "incluida"]
    ja = {r["caminho_relativo"] for r in ler(hum / "amostra.csv")} | {r["caminho_relativo"] for r in ler(hum / "outros/amostra.csv")}
    nsel = {r["caminho_relativo"]: r["n"] for r in ler(sel / "revisao.csv")}
    sug = {r["caminho_relativo"]: r for r in ler(sel / "sugestoes.csv")}
    alvo = sorted((r for r in inv if r["caminho_original"] not in ja),
                  key=lambda r: int(nsel[r["caminho_original"]]))

    # peso 1: é a população inteira que faltava, então a 10f conta direto
    gravar(out / "amostra.csv", [dict(r, n=nsel[r["caminho_original"]], caminho_relativo=r["caminho_original"],
                                      parte="restantes", estrato=f"{r['ambiente']}|{r['fogo']}", peso="1",
                                      ambiente_ia=r["ambiente"], fogo_ia=r["fogo"], fumaca_ia=r["fumaca"]) for r in alvo],
           ["n", "caminho_relativo", "split", "parte", "estrato", "peso", "ambiente_ia", "fogo_ia", "fumaca_ia", "sha256"])
    gravar(out / "sugestoes.csv", [sug[r["caminho_original"]] for r in alvo], list(next(iter(sug.values())).keys()))
    ordem = alvo[:]; random.Random(f"{a.semente}-restantes-{a.revisora}").shuffle(ordem)
    gravar(out / f"revisao_{a.revisora}.csv",
           [{"n": nsel[r["caminho_original"]], "caminho_relativo": r["caminho_original"], "classe_original": r["classe_original"],
             "motivos_revisao": "auditoria"} for r in ordem],
           ["n", "caminho_relativo", "classe_original", "motivos_revisao", "ambiente_sugerido", "fogo_sugerido",
            "fumaca_sugerida", "ambiente_confirmado", "fogo_confirmado", "fumaca_confirmada", "camera_confirmada", "observacao"])
    subprocess.run([sys.executable, str(Path(__file__).with_name("05b_pagina_revisao.py")),
                    "--origem", str(sel / "origem.json"), "--revisao", str(out / f"revisao_{a.revisora}.csv"),
                    "--sugestoes", str(out / "sugestoes.csv"), "--saida", str(out / f"revisao_{a.revisora}.html"),
                    "--exportar-como", f"revisao_humana_{a.revisora}_preenchida.csv",
                    "--chave", f"ignis_revisao_restantes_A_{a.revisora}"], check=True)
    print(f"{len(alvo)} imagens ainda só com rótulo da IA -> {out}")


if __name__ == "__main__":
    main()
