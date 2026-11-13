#!/usr/bin/env python3
"""
Etapa 9d - CONSOLIDA as condições (ponto de vista, distância do fogo, pessoas, veículos, texto, o que pode confundir
E iluminação) e mede o CLIP na auditoria cega.

A iluminação (clara, media, escura) vem da medida automática da 9a, com fonte "medida_automatica".

Cada condição final guarda a sua FONTE:
  revisao_humana  -> marcada por vocês (a 2ª volta vale sobre a 1ª)
  modelo          -> sugestão do CLIP numa imagem não revisada, quando a auditoria mostrou que ela é confiável
  nao_se_aplica   -> distância do fogo em imagem sem fogo

Como na Etapa 5c, a auditoria cega mede o acerto do modelo PARA CADA VALOR SUGERIDO (ex.: quando ele diz
"noite", quanto acerta). Se o limite inferior do IC 95% (Wilson) ficar abaixo de --confianca-min, as
imagens não revisadas com aquela sugestão vão para uma 2ª volta (revisao_condicoes_2.csv), que abre na
mesma página da 9c. Valores com poucas imagens na auditoria têm intervalo largo e também vão para revisão.

Entradas : relatorios/09_condicoes/sugestoes_condicoes.csv, revisao_condicoes_preenchida.csv,
           revisao_condicoes_2_preenchida.csv (se existir) e medidas_auto.csv (se existir)
Saídas   : relatorios/09_condicoes/
  condicoes.csv            -> uma linha por imagem incluída: condições, fonte de cada uma e medidas da 9a
  auditoria_condicoes.csv  -> acerto do modelo por atributo e por valor sugerido, com IC 95% e a decisão
  revisao_condicoes_2.csv  -> 2ª volta, se precisar (não é sobrescrito se já existir)
  resumo_condicoes.txt     -> distribuição por conjunto (treino, validação, teste): onde faltam exemplos

Uso:  python scripts/09d_consolidar_condicoes.py [--confianca-min 0.80]
"""
import argparse, csv, math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ORDEM_ATR = ("ponto_vista", "hora_dia", "ceu", "vegetacao", "agua", "pessoas", "veiculos", "texto", "confusor",
             "tipo_fogo", "distancia_fogo", "focos", "cor_chamas", "encoberto")
SO_FOGO = {"tipo_fogo", "distancia_fogo", "focos", "cor_chamas", "encoberto"}
ATR = ORDEM_ATR   # ajustado em main() às colunas que existem em sugestoes_condicoes.csv
NOME = {"iluminacao": "Iluminação (automática)", "ponto_vista": "Ponto de vista", "hora_dia": "Hora do dia", "ceu": "Céu",
        "vegetacao": "Vegetação", "agua": "Água", "pessoas": "Pessoas", "veiculos": "Veículos", "texto": "Texto/marca d'água",
        "confusor": "O que pode confundir", "tipo_fogo": "Tipo de fogo", "distancia_fogo": "Distância do fogo", "focos": "Focos",
        "cor_chamas": "Cor das chamas", "encoberto": "Fogo encoberto"}
SPLITS = ("treino", "validacao", "teste")


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
    d = "relatorios/09_condicoes"
    ap.add_argument("--sugestoes", default=f"{d}/sugestoes_condicoes.csv")
    ap.add_argument("--revisao", default=f"{d}/revisao_condicoes_preenchida.csv")
    ap.add_argument("--revisao2", default=f"{d}/revisao_condicoes_2_preenchida.csv")
    ap.add_argument("--medidas", default=f"{d}/medidas_auto.csv")
    ap.add_argument("--saida", default=d)
    ap.add_argument("--confianca-min", type=float, default=0.80)
    ap.add_argument("--forcar", action="store_true", help="permite sobrescrever revisao_condicoes_2.csv")
    a = ap.parse_args()

    sug = ler(a.sugestoes)
    global ATR
    ATR = tuple(at for at in ORDEM_ATR if f"{at}_sugerido" in sug[0])
    rev1 = ler(a.revisao)
    rev2 = ler(a.revisao2) if Path(a.revisao2).exists() else []
    med = {r["caminho_original"]: r for r in ler(a.medidas)} if Path(a.medidas).exists() else {}
    if med and "iluminacao" not in next(iter(med.values())):
        raise SystemExit("medidas_auto.csv sem a coluna iluminacao: rode a 9a de novo (versão nova).")

    # respostas humanas (2ª volta sobrescreve a 1ª, campo a campo)
    humano = defaultdict(dict)
    for lista in (rev1, rev2):
        for r in lista:
            for at in ATR:
                v = r.get(f"{at}_confirmado", "")
                if v and v != "nao_se_aplica":
                    humano[r["caminho_original"]][at] = v
    erros = []
    ids_sug = {s["caminho_original"] for s in sug}
    fora = [k for k in humano if k not in ids_sug]
    if fora: erros.append(f"{len(fora)} imagens revisadas que não estão nas sugestões (ex.: {fora[0]})")
    incompletas = [r["caminho_original"] for r in rev1 + rev2 if r.get("revisado") != "sim"]
    if erros:
        raise SystemExit("Entradas inconsistentes:\n  " + "\n  ".join(erros))

    # auditoria cega (só 1ª volta)
    aud = [r for r in rev1 if r["motivos_revisao"] == "auditoria" and r.get("quando_cego")]
    if not aud:
        print("AVISO: não há respostas cegas da auditoria (colunas *_cego): o acerto do CLIP não será medido.")
    por_sug = {s["caminho_original"]: s for s in sug}
    criterio, nao_confiavel = [], defaultdict(set)
    revisadas = set(humano)
    for at in ATR:
        valores = sorted({s[f"{at}_sugerido"] for s in sug} - {"incerto", "nao_se_aplica", ""})
        for v in valores:
            casos = [r for r in aud if por_sug[r["caminho_original"]][f"{at}_sugerido"] == v and r.get(f"{at}_cego") not in ("", "nao_se_aplica")]
            k = sum(r[f"{at}_cego"] == v for r in casos); n = len(casos)
            lo, hi = wilson(k, n)
            pend = sum(1 for s in sug if s[f"{at}_sugerido"] == v and at not in humano.get(s["caminho_original"], {}))
            decide = lo < a.confianca_min
            if decide: nao_confiavel[at].add(v)
            criterio.append({"atributo": at, "valor_sugerido": v, "auditadas": n, "acertos": k,
                             "acerto": f"{k / n:.3f}" if n else "", "ic95_inf": f"{lo:.3f}", "ic95_sup": f"{hi:.3f}",
                             "nao_revisadas_com_esta_sugestao": pend, "decisao": "revisar" if decide else "manter_sugestao"})

    # condições finais
    linhas, pend2 = [], []
    for s in sorted(sug, key=lambda s: s["caminho_original"]):
        k = s["caminho_original"]; h = humano.get(k, {})
        l = {"caminho_original": k, "split": s["split"], "ambiente": s["ambiente"], "fogo": s["fogo"]}
        precisa = []
        for at in ATR:
            sv = s[f"{at}_sugerido"]
            if at in SO_FOGO and s["fogo"] != "sim":
                val, fonte = "nao_se_aplica", "nao_se_aplica"
            elif at in h:
                val, fonte = h[at], "revisao_humana"
            elif sv not in ("incerto", "") and sv not in nao_confiavel[at]:
                val, fonte = sv, "modelo"
            else:
                val, fonte = "pendente", "pendente"
                precisa.append(at)
            l[at], l[f"fonte_{at}"] = val, fonte
        m = med.get(k, {})
        l["iluminacao"] = m.get("iluminacao", "") or "sem_medida"
        l["fonte_iluminacao"] = "medida_automatica" if m.get("iluminacao") else "sem_medida"
        for c in ("brilho", "contraste", "saturacao", "nitidez", "pct_escuro", "pct_tons_fogo", "faixa_brilho", "faixa_nitidez"):
            l[c] = m.get(c, "")
        linhas.append(l)
        if precisa: pend2.append((s, precisa))

    saida = Path(a.saida); saida.mkdir(parents=True, exist_ok=True)
    gravar(saida / "condicoes.csv", linhas, list(linhas[0].keys()))
    gravar(saida / "auditoria_condicoes.csv", criterio, ["atributo", "valor_sugerido", "auditadas", "acertos", "acerto", "ic95_inf",
                                                          "ic95_sup", "nao_revisadas_com_esta_sugestao", "decisao"])

    destino = None
    if pend2:
        out = []
        for n, (s, precisa) in enumerate(sorted(pend2, key=lambda t: t[0]["caminho_original"]), 1):
            o = {"n": n, "caminho_original": s["caminho_original"], "motivos_revisao": "nao_confiavel"}
            for at in ATR: o[f"{at}_sugerido"] = s[f"{at}_sugerido"]
            for at in ATR: o[f"{at}_confirmado"] = humano.get(s["caminho_original"], {}).get(at, "")
            o["observacao"] = "rever: " + ", ".join(NOME[x] for x in precisa)
            out.append(o)
        destino = saida / "revisao_condicoes_2.csv"
        if destino.exists() and not a.forcar:
            destino = saida / "revisao_condicoes_2_novo.csv"
            print(f"AVISO: revisao_condicoes_2.csv já existe e NÃO foi sobrescrito. Nova versão em {destino.name}")
        gravar(destino, out, list(out[0].keys()))

    txt = [f"Etapa 9d gerada em {datetime.now(timezone.utc).isoformat(timespec='seconds')} | NADA NO DATASET FOI ALTERADO",
           f"imagens: {len(linhas)} | revisadas por vocês: {len(revisadas)} | auditoria cega: {len(aud)}",
           f"critério: revisar o valor sugerido quando o limite inferior do IC 95% (Wilson) < {a.confianca_min}", "",
           "Acerto do CLIP na auditoria cega, por valor sugerido:"]
    for c in criterio:
        txt.append(f"  {c['atributo']:15s} {c['valor_sugerido']:11s} {c['acertos']:>3}/{c['auditadas']:<3} "
                   f"IC {float(c['ic95_inf']):4.0%} a {float(c['ic95_sup']):4.0%}  não revisadas: {c['nao_revisadas_com_esta_sugestao']:4d}  {c['decisao']}")
    segs = sorted(float(r["segundos_cego"]) for r in aud if r.get("segundos_cego"))
    if segs:
        med_s = segs[len(segs) // 2]
        txt += ["", f"Tempo até a resposta cega: mediana {med_s:.1f} s (mín. {segs[0]:.1f} s, máx. {segs[-1]:.1f} s)"]
        if med_s < 4:
            txt.append("  ATENÇÃO: respostas muito rápidas. Confira se as imagens foram de fato olhadas antes de usar a auditoria.")
    txt += ["", "Fontes:"]
    for at in ATR:
        txt.append(f"  {NOME[at]:18s} {dict(Counter(l[f'fonte_{at}'] for l in linhas))}")
    for at in ATR + ("iluminacao",):
        txt += ["", f"{NOME[at]} por conjunto:"]
        vals = sorted({l[at] for l in linhas})
        txt.append("  " + f"{'':12s}" + "".join(f"{v:>14s}" for v in vals))
        for s in SPLITS:
            c = Counter(l[at] for l in linhas if l["split"] == s)
            txt.append("  " + f"{s:12s}" + "".join(f"{c[v]:>14d}" for v in vals))
    if incompletas:
        txt += ["", f"ATENÇÃO: {len(incompletas)} linhas dos CSVs de revisão não estão completas (revisado != sim)."]
    if pend2:
        txt += ["", f"{len(pend2)} imagens ainda sem condição confiável -> {destino}",
                f"Próximo passo: python scripts/09c_pagina_condicoes.py --revisao {destino.as_posix()}"]
    else:
        txt += ["", "Todas as imagens têm condição definida."]
    (saida / "resumo_condicoes.txt").write_text("\n".join(txt) + "\n", encoding="utf-8")
    print("\n".join(txt))


if __name__ == "__main__":
    main()
