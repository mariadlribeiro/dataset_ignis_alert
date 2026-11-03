#!/usr/bin/env python3
"""
Etapa 5d - CONSOLIDAÇÃO dos rótulos: junta revisões humanas, sugestões do modelo e decisões (SOMENTE LEITURA).

Regras (na ordem de prioridade, campo a campo):
  1. revisão humana (1ª revisão completa ou 2ª revisão só de ambiente) prevalece sobre o modelo;
  2. cópia exata (mesmo SHA-256) de uma imagem revisada herda o rótulo humano daquele campo;
  3. o que sobrar fica com a sugestão do modelo, marcada como fonte "modelo" (não revisada).
  Nada é inventado: tipo de imagem nunca visto por uma pessoa fica "nao_verificado".

Entradas : 03_duplicatas/imagem_grupo.csv, 05_sugestoes/sugestoes.csv, revisao_preenchida.csv,
           revisao_ambiente_preenchida.csv (opcional), 04_divisao/decisoes_revisao.csv (opcional)
Saídas   : relatorios/05_consolidacao/
  rotulos.csv          -> uma linha por imagem: rótulo final de cada campo e a FONTE de cada um
  auditoria_modelo.csv -> acerto do modelo na auditoria cega (IC 95% de Wilson) e na 2ª revisão
  conferir.csv         -> grupos de quase duplicatas com rótulos diferentes entre si (para olhar)
  resumo.txt           -> contagens finais

Uso:  python scripts/05d_consolidar.py
"""
import argparse, csv, json, math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

CAMPOS = ("ambiente", "fogo", "fumaca")
COL_CONF = {"ambiente": "ambiente_confirmado", "fogo": "fogo_confirmado", "fumaca": "fumaca_confirmada"}
COL_SUG = {"ambiente": "ambiente_sugerido", "fogo": "fogo_sugerido", "fumaca": "fumaca_sugerida"}
VALIDOS = {"ambiente": {"floresta", "cidade", "casa", "predios", "flores_jardins", "outros", "ambiente_incerto"},
           "fogo": {"sim", "nao", "incerto"}, "fumaca": {"sim", "nao", "incerto"},
           "tipo_imagem": {"fotografia", "sintetica", "visualizacao_sensor"}}


def ler(caminho):
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def ler_opcional(caminho):
    return ler(caminho) if Path(caminho).exists() else []


def gravar(caminho, linhas, cols):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(linhas)


def wilson(k, n, z=1.96):
    if n == 0:
        return float("nan"), float("nan")
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - m), min(1.0, c + m)


def pasta_tem_fogo(classe):
    return "non_fire" not in classe.lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grupos", default="relatorios/03_duplicatas/imagem_grupo.csv")
    ap.add_argument("--sugestoes", default="relatorios/05_sugestoes/sugestoes.csv")
    ap.add_argument("--revisao", default="relatorios/05_sugestoes/revisao_preenchida.csv")
    ap.add_argument("--revisao-ambiente", default="relatorios/05_sugestoes/revisao_ambiente_preenchida.csv")
    ap.add_argument("--decisoes", default="relatorios/04_divisao/decisoes_revisao.csv")
    ap.add_argument("--saida", default="relatorios/05_consolidacao")
    a = ap.parse_args()

    imagens = ler(a.grupos)
    sug = {r["caminho_relativo"]: r for r in ler(a.sugestoes)}
    rev1 = {r["caminho_relativo"]: r for r in ler(a.revisao)}
    rev2 = {r["caminho_relativo"]: r for r in ler_opcional(a.revisao_ambiente)}
    dec = {r["caminho_relativo"]: r for r in ler_opcional(a.decisoes)}

    # ---------- validações de entrada ----------
    erros = []
    falta_sug = [r["caminho_relativo"] for r in imagens if r["caminho_relativo"] not in sug]
    if falta_sug: erros.append(f"{len(falta_sug)} imagens sem sugestão do modelo (ex.: {falta_sug[0]})")
    dupl = set(rev1) & set(rev2)
    if dupl: erros.append(f"{len(dupl)} imagens aparecem nas duas revisões (ex.: {next(iter(dupl))})")
    for nome, rev, obrig in (("revisao_preenchida", rev1, CAMPOS), ("revisao_ambiente_preenchida", rev2, ("ambiente",))):
        nao = [k for k, r in rev.items() if r.get("revisado") != "sim"]
        if nao: erros.append(f"{nome}: {len(nao)} linhas com revisado != sim (ex.: {nao[0]})")
        for k, r in rev.items():
            for c in obrig:
                if r[COL_CONF[c]] not in VALIDOS[c]:
                    erros.append(f"{nome}: valor inválido em {COL_CONF[c]} = '{r[COL_CONF[c]]}' ({k})"); break
    if erros:
        raise SystemExit("Entradas inconsistentes:\n  " + "\n  ".join(erros))

    # ---------- 1ª passada: rótulo e fonte de cada campo ----------
    linhas = []
    for img in imagens:
        k = img["caminho_relativo"]; s = sug[k]
        l = {"caminho_relativo": k, "classe_original": img["classe_original"], "id_grupo": img["id_grupo"],
             "sha256": img["sha256"]}
        if k in rev1:
            r = rev1[k]; situacao = "revisada_completa"
            for c in CAMPOS:
                l[c], l["fonte_" + c] = r[COL_CONF[c]], "revisao_humana"
            l["tipo_imagem"], l["fonte_tipo"] = r["tipo_imagem"] or "fotografia", "revisao_humana"
            l["camera"], l["observacao"] = r.get("camera_confirmada", ""), r.get("observacao", "")
        elif k in rev2:
            r = rev2[k]; situacao = "revisada_ambiente"
            for c in CAMPOS:
                if r[COL_CONF[c]]:
                    l[c], l["fonte_" + c] = r[COL_CONF[c]], "revisao_humana"
                else:
                    l[c], l["fonte_" + c] = s[COL_SUG[c]], "modelo"
            l["tipo_imagem"], l["fonte_tipo"] = r["tipo_imagem"] or "fotografia", "revisao_humana"
            l["camera"], l["observacao"] = r.get("camera_confirmada", ""), r.get("observacao", "")
        else:
            situacao = "nao_revisada"
            for c in CAMPOS:
                l[c], l["fonte_" + c] = s[COL_SUG[c]], "modelo"
            l["tipo_imagem"], l["fonte_tipo"], l["camera"], l["observacao"] = "nao_verificado", "nenhuma", "", ""
        l["situacao"] = situacao
        l["camera_sugerida_fraca"] = s["camera_sugerida_fraca"]
        d = dec.get(k, {})
        l["decisao"], l["justificativa_decisao"] = d.get("decisao", ""), d.get("justificativa", "")
        linhas.append(l)

    # ---------- 2ª passada: cópias exatas herdam o rótulo humano ----------
    por_sha = defaultdict(list)
    for l in linhas: por_sha[l["sha256"]].append(l)
    herdadas, conflitos_exatos = Counter(), []
    for sha, ms in por_sha.items():
        if len(ms) < 2: continue
        for c in CAMPOS + ("tipo",):
            campo = "tipo_imagem" if c == "tipo" else c
            humanos = {m[campo] for m in ms if m["fonte_" + c] == "revisao_humana"}
            if len(humanos) > 1:
                conflitos_exatos.append((sha, campo, sorted(humanos), [m["caminho_relativo"] for m in ms]))
            elif len(humanos) == 1:
                v = next(iter(humanos))
                for m in ms:
                    if m["fonte_" + c] in ("modelo", "nenhuma"):
                        m[campo], m["fonte_" + c] = v, "copia_exata"; herdadas[campo] += 1

    for l in linhas:
        l["pasta_diverge_do_fogo"] = ("sim" if l["fogo"] in ("sim", "nao") and
                                      (l["fogo"] == "sim") != pasta_tem_fogo(l["classe_original"]) else "nao")

    # ---------- grupos de quase duplicatas com rótulos diferentes ----------
    por_grupo = defaultdict(list)
    for l in linhas: por_grupo[l["id_grupo"]].append(l)
    conferir = []
    for g, ms in sorted(por_grupo.items()):
        if len(ms) < 2: continue
        difs = [c for c in ("ambiente", "fogo") if len({m[c] for m in ms}) > 1]
        if not difs: continue
        justificado = all(m["decisao"] == "incluir" for m in ms)
        for m in ms:
            conferir.append({"id_grupo": g, "campos_diferentes": "|".join(difs), "caminho_relativo": m["caminho_relativo"],
                             "ambiente": m["ambiente"], "fonte_ambiente": m["fonte_ambiente"],
                             "fogo": m["fogo"], "fonte_fogo": m["fonte_fogo"],
                             "situacao": "decisao_registrada" if justificado else "conferir"})
    grupos_conferir = {c["id_grupo"] for c in conferir if c["situacao"] == "conferir"}
    for l in linhas:
        l["conferir"] = "quase_duplicata_com_rotulo_diferente" if l["id_grupo"] in grupos_conferir else ""

    # ---------- acerto do modelo ----------
    aud = [r for r in rev1.values() if r["motivos_revisao"] == "auditoria" and r.get("ambiente_cego")]
    metricas = []
    for c in CAMPOS:
        kk = sum(r[c + "_cego"] == r[COL_SUG[c]] for r in aud); n = len(aud); lo, hi = wilson(kk, n)
        metricas.append({"origem": "auditoria_cega", "campo": c, "recorte": "todas", "acertos": kk, "n": n,
                         "acerto": round(kk / n, 4) if n else "", "ic95_inf": round(lo, 4), "ic95_sup": round(hi, 4)})
    for amb in sorted({r["ambiente_sugerido"] for r in aud}):
        sub = [r for r in aud if r["ambiente_sugerido"] == amb]
        kk = sum(r["ambiente_cego"] == amb for r in sub); lo, hi = wilson(kk, len(sub))
        metricas.append({"origem": "auditoria_cega", "campo": "ambiente", "recorte": f"sugerido={amb}", "acertos": kk,
                         "n": len(sub), "acerto": round(kk / len(sub), 4), "ic95_inf": round(lo, 4), "ic95_sup": round(hi, 4)})
    for amb in sorted({r["ambiente_sugerido"] for r in rev2.values()}):
        sub = [r for r in rev2.values() if r["ambiente_sugerido"] == amb]
        kk = sum(r["ambiente_confirmado"] == amb for r in sub); lo, hi = wilson(kk, len(sub))
        metricas.append({"origem": "revisao_ambiente", "campo": "ambiente", "recorte": f"sugerido={amb}", "acertos": kk,
                         "n": len(sub), "acerto": round(kk / len(sub), 4), "ic95_inf": round(lo, 4), "ic95_sup": round(hi, 4)})

    # ---------- gravação ----------
    saida = Path(a.saida); saida.mkdir(parents=True, exist_ok=True)
    cols = ["caminho_relativo", "classe_original", "id_grupo", "sha256", "situacao",
            "ambiente", "fonte_ambiente", "fogo", "fonte_fogo", "fumaca", "fonte_fumaca",
            "tipo_imagem", "fonte_tipo", "camera", "camera_sugerida_fraca", "pasta_diverge_do_fogo",
            "decisao", "justificativa_decisao", "conferir", "observacao"]
    linhas.sort(key=lambda l: l["caminho_relativo"])
    gravar(saida / "rotulos.csv", linhas, cols)
    gravar(saida / "auditoria_modelo.csv", metricas, list(metricas[0].keys()))
    gravar(saida / "conferir.csv", conferir, ["id_grupo", "campos_diferentes", "caminho_relativo", "ambiente",
                                              "fonte_ambiente", "fogo", "fonte_fogo", "situacao"])

    fonte = lambda c: Counter(l["fonte_" + c] for l in linhas)
    txt = [f"Consolidação gerada em {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
           f"imagens: {len(linhas)} | situação: {dict(Counter(l['situacao'] for l in linhas))}",
           f"fonte do ambiente: {dict(fonte('ambiente'))}",
           f"fonte do fogo: {dict(fonte('fogo'))}",
           f"fonte da fumaça: {dict(fonte('fumaca'))}",
           f"fonte do tipo: {dict(fonte('tipo'))}",
           f"herdados de cópia exata: {dict(herdadas)}",
           f"conflitos entre cópias exatas revisadas: {len(conflitos_exatos)}",
           f"ambiente: {dict(Counter(l['ambiente'] for l in linhas))}",
           f"fogo: {dict(Counter(l['fogo'] for l in linhas))}",
           f"fumaça: {dict(Counter(l['fumaca'] for l in linhas))}",
           f"tipo de imagem: {dict(Counter(l['tipo_imagem'] for l in linhas))}",
           f"pasta original diverge do fogo: {sum(l['pasta_diverge_do_fogo'] == 'sim' for l in linhas)}",
           f"decisões: {dict(Counter(l['decisao'] for l in linhas if l['decisao']))}",
           f"grupos para conferir (quase duplicatas com rótulo diferente): {len(grupos_conferir)}",
           "", "Acerto do modelo:"]
    for m in metricas:
        txt.append(f"  {m['origem']:17s} {m['campo']:9s} {m['recorte']:22s} {m['acertos']:>4}/{m['n']:<4} "
                   f"{float(m['acerto']):6.1%}  IC95 {m['ic95_inf']:.1%} a {m['ic95_sup']:.1%}")
    for sha, campo, vals, ms in conflitos_exatos:
        txt.append(f"ATENÇÃO: cópias exatas com {campo} diferente {vals}: {ms}")
    (saida / "resumo.txt").write_text("\n".join(txt) + "\n", encoding="utf-8")
    print("\n".join(txt))
    print(f"\nSaídas em {saida}. Nada foi alterado no dataset.")


if __name__ == "__main__":
    main()
