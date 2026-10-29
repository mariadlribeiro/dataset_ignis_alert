#!/usr/bin/env python3
"""
Etapa 4 - Divisão treino/validação/teste POR GRUPO, sem vazamento (SOMENTE LEITURA).

Regras:
  * a unidade de divisão é o id_grupo (Etapa 3): cópias e quase duplicatas ficam no mesmo conjunto;
  * estratificada pela classe original (proporção de fogo/sem fogo mantida em cada conjunto);
  * semente fixa -> resultado reproduzível;
  * ficam FORA da divisão (em pendentes.csv, nada é excluído): grupos com conflito de rótulo
    e GIFs animados. Para liberar um caso depois da revisão manual, use --decisoes.

Entradas : relatorios/03_duplicatas/imagem_grupo.csv, conflitos_rotulo.csv, 02_validacao/validacao.csv
Saídas   : relatorios/04_divisao/
  divisao.csv                      -> caminho_relativo, classe_original, id_grupo, split
  pendentes.csv                    -> o que ficou fora e por quê
  resumo_divisao.csv               -> contagens e proporções por split x classe
  pares_proximos_entre_splits.csv  -> pares de imagens parecidas (Hamming <= --aviso) em splits diferentes
  verificacao.txt                  -> resultado das verificações de vazamento

Decisões manuais (opcional), CSV com colunas: caminho_relativo,decisao  (incluir | excluir)
  incluir -> a imagem volta para a divisão com a classe original; excluir -> fica de fora (documentado).

Uso:  python scripts/04_divisao.py [--treino 0.70 --val 0.15 --teste 0.15 --semente 42]
"""
import argparse, csv, json, random
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image

SPLITS = ("treino", "validacao", "teste")


def ler(caminho):
    with open(caminho, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def gravar(caminho, linhas, cols):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(linhas)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--origem", default="relatorios/01_origem/origem.json")
    ap.add_argument("--grupos", default="relatorios/03_duplicatas/imagem_grupo.csv")
    ap.add_argument("--conflitos", default="relatorios/03_duplicatas/conflitos_rotulo.csv")
    ap.add_argument("--validacao", default="relatorios/02_validacao/validacao.csv")
    ap.add_argument("--decisoes", default="relatorios/04_divisao/decisoes_revisao.csv")
    ap.add_argument("--saida", default="relatorios/04_divisao")
    ap.add_argument("--treino", type=float, default=0.70)
    ap.add_argument("--val", type=float, default=0.15)
    ap.add_argument("--teste", type=float, default=0.15)
    ap.add_argument("--semente", type=int, default=42)
    ap.add_argument("--aviso", type=int, default=8, help="Hamming p/ listar pares próximos entre splits")
    a = ap.parse_args()
    if abs(a.treino + a.val + a.teste - 1) > 1e-6:
        raise SystemExit("As proporções precisam somar 1.")
    prop = dict(zip(SPLITS, (a.treino, a.val, a.teste)))

    raiz = Path(json.loads(Path(a.origem).read_text(encoding="utf-8"))["caminho_local"])
    saida = Path(a.saida); saida.mkdir(parents=True, exist_ok=True)
    imagens = ler(a.grupos)
    val = {r["caminho_relativo"]: r for r in ler(a.validacao)}
    conflito = {r["caminho_relativo"] for r in ler(a.conflitos)} if Path(a.conflitos).exists() else set()
    decisoes = {r["caminho_relativo"]: r["decisao"].strip().lower()
                for r in ler(a.decisoes)} if Path(a.decisoes).exists() else {}

    # --- pendentes ---
    pendentes, incluidas = [], []
    for r in imagens:
        rel, motivo = r["caminho_relativo"], ""
        if rel in conflito:
            motivo = "grupo com conflito de rotulo (classes originais diferentes)"
        elif val.get(rel, {}).get("formato_real") == "GIF":
            with Image.open(raiz / rel) as im:
                if getattr(im, "n_frames", 1) > 1:
                    motivo = f"GIF animado ({im.n_frames} quadros)"
        dec = decisoes.get(rel, "")
        if motivo and dec != "incluir":
            pendentes.append({"caminho_relativo": rel, "classe_original": r["classe_original"],
                              "id_grupo": r["id_grupo"], "motivo": motivo,
                              "decisao": dec or "pendente"})
        elif dec == "excluir":
            pendentes.append({"caminho_relativo": rel, "classe_original": r["classe_original"],
                              "id_grupo": r["id_grupo"], "motivo": "excluida por decisao manual",
                              "decisao": "excluir"})
        else:
            incluidas.append(r)

    # --- divisão por grupo, estratificada pela classe majoritária do grupo ---
    grupos = defaultdict(list)
    for r in incluidas: grupos[r["id_grupo"]].append(r)
    estratos = defaultdict(list)
    for g, ms in grupos.items():
        classe = Counter(m["classe_original"] for m in ms).most_common(1)[0][0]
        estratos[classe].append((g, len(ms)))

    rnd = random.Random(a.semente)
    destino = {}
    for classe in sorted(estratos):
        lista = sorted(estratos[classe])            # ordem estável antes de embaralhar
        rnd.shuffle(lista)
        lista.sort(key=lambda x: -x[1])              # grupos grandes primeiro (sort estável)
        total = sum(n for _, n in lista); atual = Counter()
        for g, n in lista:
            s = max(SPLITS, key=lambda k: (prop[k] * total - atual[k]) / max(prop[k] * total, 1e-9))
            destino[g] = s; atual[s] += n

    linhas = [{"caminho_relativo": r["caminho_relativo"], "classe_original": r["classe_original"],
               "id_grupo": r["id_grupo"], "split": destino[r["id_grupo"]]} for r in incluidas]
    linhas.sort(key=lambda x: (x["split"], x["classe_original"], x["caminho_relativo"]))
    gravar(saida / "divisao.csv", linhas, ["caminho_relativo", "classe_original", "id_grupo", "split"])
    gravar(saida / "pendentes.csv", pendentes, ["caminho_relativo", "classe_original", "id_grupo", "motivo", "decisao"])

    # --- resumo ---
    cont = Counter((l["split"], l["classe_original"]) for l in linhas)
    tot_classe = Counter(l["classe_original"] for l in linhas)
    resumo = [{"split": s, "classe_original": c, "imagens": cont[(s, c)],
               "proporcao_da_classe": round(cont[(s, c)] / tot_classe[c], 3)}
              for s in SPLITS for c in sorted(tot_classe)]
    gravar(saida / "resumo_divisao.csv", resumo, ["split", "classe_original", "imagens", "proporcao_da_classe"])

    # --- verificações de vazamento ---
    sha = {r["caminho_relativo"]: r["sha256"] for r in imagens}
    dh = {r["caminho_relativo"]: int(r["dhash"], 16) for r in imagens}
    msgs, ok = [], True
    g_splits = defaultdict(set); h_splits = defaultdict(set)
    for l in linhas:
        g_splits[l["id_grupo"]].add(l["split"]); h_splits[sha[l["caminho_relativo"]]].add(l["split"])
    viol_g = [g for g, s in g_splits.items() if len(s) > 1]
    viol_h = [h for h, s in h_splits.items() if len(s) > 1]
    msgs.append(f"grupos em mais de um split: {len(viol_g)} {'OK' if not viol_g else 'FALHA'}")
    msgs.append(f"arquivos identicos (SHA-256) em mais de um split: {len(viol_h)} {'OK' if not viol_h else 'FALHA'}")
    ok = not viol_g and not viol_h
    msgs.append(f"imagens divididas: {len(linhas)} | pendentes/excluidas: {len(pendentes)} | total: {len(imagens)}")
    msgs.append(f"soma confere: {len(linhas) + len(pendentes) == len(imagens)}")

    pares = []
    for i in range(len(linhas)):
        hi = dh[linhas[i]["caminho_relativo"]]
        for j in range(i + 1, len(linhas)):
            if linhas[i]["split"] != linhas[j]["split"]:
                d = (hi ^ dh[linhas[j]["caminho_relativo"]]).bit_count()
                if d <= a.aviso:
                    pares.append({"imagem_a": linhas[i]["caminho_relativo"], "split_a": linhas[i]["split"],
                                  "imagem_b": linhas[j]["caminho_relativo"], "split_b": linhas[j]["split"],
                                  "hamming": d})
    pares.sort(key=lambda p: p["hamming"])
    gravar(saida / "pares_proximos_entre_splits.csv", pares,
           ["imagem_a", "split_a", "imagem_b", "split_b", "hamming"])
    msgs.append(f"pares parecidos (Hamming <= {a.aviso}) em splits diferentes: {len(pares)} (revisar se > 0)")
    (saida / "verificacao.txt").write_text("\n".join(msgs) + "\n", encoding="utf-8")

    print("Divisão por split e classe:")
    for r in resumo:
        print(f"  {r['split']:10s} {r['classe_original']:32s} {r['imagens']:4d}  ({r['proporcao_da_classe']:.1%})")
    print("\nVerificações:"); [print("  " + m) for m in msgs]
    print(f"\nSemente: {a.semente}. Nada foi alterado no dataset.")
    if not ok: raise SystemExit("VAZAMENTO DETECTADO - veja verificacao.txt")


if __name__ == "__main__":
    main()