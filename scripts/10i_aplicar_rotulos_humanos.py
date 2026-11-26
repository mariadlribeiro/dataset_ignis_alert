#!/usr/bin/env python3
"""
Etapa 10i - APLICA os rótulos da revisão humana (10e, 10g, 10h, 10j) às imagens da 2ª fonte.

Decisão de 25/11/2026: manter todas as imagens e corrigir os números (a floresta deixa de ser 510 = 510).

Rótulo final de cada imagem revisada, nesta ordem de prioridade:
  1) desempate (revisao_humana_A/desempate_preenchido.csv);
  2) resposta cega da revisora (revisao_humana_A/, outros/ e restantes/).
Aplica AMBIENTE e FUMAÇA. FOGO só muda quando o rótulo humano é 'sim' ou 'nao' e diferente do da IA (nenhum caso hoje);
fogo 'incerto' NÃO é aplicado e fica listado em pendencias.csv para decisão humana. As imagens sem revisão humana
continuam com o rótulo da IA (fonte_* = revisao_ia).

Pendências: decisões humanas sobre os casos de pendencias.csv vão em rotulos_humanos_A/decisoes_pendencias.csv
(caminho_original, ambiente, fogo, fumaca, motivo) e são aplicadas na próxima execução.

Dois modos:
  python scripts/10i_aplicar_rotulos_humanos.py
      atualiza relatorios/10_nova_fonte/inventario_combinado.csv (ambiente, fumaça, fontes e destino) e grava
      relatorios/10_nova_fonte/rotulos_humanos_A/ (mudancas.csv, pendencias.csv, resumo.txt). Não mexe em imagens.
      Se o inventário já estiver atualizado, não muda nada (pode rodar de novo).
  python scripts/10i_aplicar_rotulos_humanos.py --mover
      no computador com as imagens: move cada arquivo da pasta antiga para a do novo ambiente
      (data/dataset_organizado/<ambiente>/<com|sem>_fogo/), confere o SHA-256 e grava o inventário atualizado em
      data/dataset_organizado/inventario.csv (o anterior fica em inventario_antes_10i.csv).
Depois do --mover, rode de novo a Etapa 11 (exportar) para o estratos.csv ter os ambientes novos. A divisão
treino/validação/teste e as classes com fogo/sem fogo não mudam.
"""
import argparse, csv, hashlib, shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

NOME = "cristiancristancho_forest-fire-image-dataset"
SPLITS = ["treino", "validacao", "teste"]
AMBS = ["floresta", "predios", "cidade", "casa", "outros"]


def ler(caminho):
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def gravar(caminho, linhas, cols):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore", lineterminator="\n"); w.writeheader(); w.writerows(linhas)


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def rotulos_humanos(hum):
    final = {}
    for arq in [hum / "revisao_humana_revisora_preenchida.csv", hum / "outros/revisao_humana_revisora_preenchida.csv",
                hum / "restantes/revisao_humana_revisora_preenchida.csv"]:
        if not arq.exists(): continue  # restantes/ (10j) só existe depois da revisão
        for r in ler(arq):
            if all(r.get(f"{c}_cego") for c in ("ambiente", "fogo", "fumaca")):
                final[r["caminho_relativo"]] = {c: r[f"{c}_cego"] for c in ("ambiente", "fogo", "fumaca")} | {"origem": "cega"}
    for r in ler(hum / "desempate_preenchido.csv"):
        if r["decidida"] == "sim":
            final[r["caminho_relativo"]] = {c: r[f"{c}_final"] for c in ("ambiente", "fogo", "fumaca")} | {"origem": "desempate"}
    return final


def tabela(inv):
    inc = [r for r in inv if r["situacao"] == "incluida"]
    c = Counter((r["split"], r["ambiente"], r["fogo"]) for r in inc)
    L = [f"  {'ambiente':10s} " + " ".join(f"{s:>13s}" for s in SPLITS) + f" {'total':>13s}"]
    for amb in AMBS:
        cel = [(c[(s, amb, 'sim')], c[(s, amb, 'nao')]) for s in SPLITS]
        L.append(f"  {amb:10s} " + " ".join(f"{x[0]:6d}/{x[1]:<6d}" for x in cel)
                 + f" {sum(x[0] for x in cel):6d}/{sum(x[1] for x in cel):<6d}")
    tf = Counter(r["fogo"] for r in inc)
    return L + [f"  TOTAL incluídas: {len(inc)} | com fogo {tf['sim']} | sem fogo {tf['nao']}"]


def main():
    base = Path("relatorios/10_nova_fonte")
    ap = argparse.ArgumentParser()
    ap.add_argument("--combinado", default=str(base / "inventario_combinado.csv"))
    ap.add_argument("--humana", default=str(base / NOME / "revisao_humana_A"))
    ap.add_argument("--saida", default=str(base / "rotulos_humanos_A"))
    ap.add_argument("--destino", default="data/dataset_organizado")
    ap.add_argument("--mover", action="store_true", help="move as imagens no disco (computador com o dataset)")
    a = ap.parse_args()
    out = Path(a.saida); out.mkdir(parents=True, exist_ok=True)
    comb_path = Path(a.combinado)
    inv = ler(comb_path); cols = list(inv[0].keys())

    if a.mover:
        mud = ler(out / "mudancas.csv"); movidas = ja = 0
        for m in mud:
            if m["destino_antigo"] == m["destino_novo"]: continue
            src, dst = Path(m["destino_antigo"]), Path(m["destino_novo"])
            if dst.exists():
                if sha256(dst) != m["sha256"]: raise SystemExit(f"Já existe um arquivo DIFERENTE em {dst}; nada foi movido.")
                ja += 1; continue
            if not src.exists(): raise SystemExit(f"Não achei {src} (nem {dst}).")
            if sha256(src) != m["sha256"]: raise SystemExit(f"SHA diferente do inventário: {src}")
            dst.parent.mkdir(parents=True, exist_ok=True); shutil.move(str(src), str(dst))
            if sha256(dst) != m["sha256"]: raise SystemExit(f"SHA não confere depois de mover: {dst}")
            movidas += 1
        inv_local = Path(a.destino) / "inventario.csv"
        if inv_local.exists(): shutil.copyfile(inv_local, Path(a.destino) / "inventario_antes_10i.csv")
        shutil.copyfile(comb_path, inv_local)
        print(f"movidas agora: {movidas} | já estavam no lugar: {ja} | inventário local atualizado: {inv_local}")
        return

    fin = rotulos_humanos(Path(a.humana))
    mud, pend = [], []
    antes = [dict(r) for r in inv]
    for r in inv:
        if not r["dataset"].startswith("cristiancristancho") or r["caminho_original"] not in fin: continue
        f = fin[r["caminho_original"]]
        if r["fonte_ambiente"] in ("revisao_humana", "decisao_humana"):   # já aplicado antes
            continue
        velho = dict(r)
        r["ambiente"], r["fumaca"] = f["ambiente"], f["fumaca"]
        r["fonte_ambiente"] = r["fonte_fumaca"] = "revisao_humana"
        if f["fogo"] in ("sim", "nao"):
            r["fogo"], r["fonte_fogo"] = f["fogo"], "revisao_humana"
        else:
            pend.append({"caminho_original": r["caminho_original"], "split": r["split"], "campo": "fogo",
                         "rotulo_ia": velho["fogo"], "rotulo_humano": f["fogo"], "situacao": "mantido o da IA até decisão"})
        r["destino"] = f"{a.destino}/{r['ambiente']}/{'com_fogo' if r['fogo'] == 'sim' else 'sem_fogo'}/{r['nome_novo']}"
        mud.append({"caminho_original": r["caminho_original"], "split": r["split"], "sha256": r["sha256"], "origem": f["origem"],
                    "ambiente_ia": velho["ambiente"], "ambiente_final": r["ambiente"], "fogo_ia": velho["fogo"], "fogo_final": r["fogo"],
                    "fumaca_ia": velho["fumaca"], "fumaca_final": r["fumaca"],
                    "destino_antigo": velho["destino"], "destino_novo": r["destino"]})
    # decisões das pendências (decisoes_pendencias.csv): valem por cima de tudo e podem ser aplicadas depois
    dec_path = out / "decisoes_pendencias.csv"
    decs = {d["caminho_original"]: d for d in ler(dec_path)} if dec_path.exists() else {}
    novas_dec = []
    for r in inv:
        d = decs.get(r["caminho_original"])
        if not d or not r["dataset"].startswith("cristiancristancho"): continue
        if all(r[c] == d[c] for c in ("ambiente", "fogo", "fumaca")) and r["fonte_ambiente"] == "decisao_humana": continue
        velho = dict(r)
        for c in ("ambiente", "fogo", "fumaca"): r[c] = d[c]; r[f"fonte_{c}"] = "decisao_humana"
        r["destino"] = f"{a.destino}/{r['ambiente']}/{'com_fogo' if r['fogo'] == 'sim' else 'sem_fogo'}/{r['nome_novo']}"
        novas_dec.append({"caminho_original": r["caminho_original"], "split": r["split"], "sha256": r["sha256"], "origem": "decisao_pendencia",
                          "ambiente_ia": velho["ambiente"], "ambiente_final": r["ambiente"], "fogo_ia": velho["fogo"], "fogo_final": r["fogo"],
                          "fumaca_ia": velho["fumaca"], "fumaca_final": r["fumaca"],
                          "destino_antigo": velho["destino"], "destino_novo": r["destino"]})
    for p_ in pend:
        if p_["caminho_original"] in decs: p_["situacao"] = "decidido: " + decs[p_["caminho_original"]]["motivo"]
    if not mud and not novas_dec:
        print("Nada a aplicar: o inventário combinado já tem os rótulos humanos e as decisões."); return
    gravar(comb_path, inv, cols)
    if mud:
        gravar(out / "pendencias.csv", pend, ["caminho_original", "split", "campo", "rotulo_ia", "rotulo_humano", "situacao"])
    else:   # rodada só com decisões novas: acrescenta ao que já foi aplicado
        mud = ler(out / "mudancas.csv")
        pend = ler(out / "pendencias.csv")
        for p_ in pend:
            if p_["caminho_original"] in decs: p_["situacao"] = "decidido: " + decs[p_["caminho_original"]]["motivo"]
        gravar(out / "pendencias.csv", pend, ["caminho_original", "split", "campo", "rotulo_ia", "rotulo_humano", "situacao"])
        gravar(out / "mudancas.csv", mud + novas_dec, list(mud[0].keys()))
        txt = ["", f"Decisões das pendências aplicadas em {datetime.now(timezone.utc).isoformat(timespec='seconds')}:"]
        txt += [f"  {d['caminho_original']} ({d['split']}): ambiente {d['ambiente_ia']} -> {d['ambiente_final']}, "
                f"fogo {d['fogo_final']}, fumaça {d['fumaca_final']}" for d in novas_dec]
        txt += ["", "Dataset combinado DEPOIS das decisões:"] + tabela(inv) + \
               ["", "Para levar ao disco: python scripts/10i_aplicar_rotulos_humanos.py --mover"]
        with open(out / "resumo.txt", "a", encoding="utf-8") as f: f.write("\n".join(txt) + "\n")
        print("\n".join(txt)); return
    mud = mud + novas_dec
    gravar(out / "mudancas.csv", mud, list(mud[0].keys()))
    n_amb = sum(m["ambiente_ia"] != m["ambiente_final"] for m in mud)
    n_fum = sum(m["fumaca_ia"] != m["fumaca_final"] for m in mud)
    n_fogo = sum(m["fogo_ia"] != m["fogo_final"] for m in mud)
    n_mov = sum(m["destino_antigo"] != m["destino_novo"] for m in mud)
    txt = [f"Etapa 10i gerada em {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
           f"rótulo humano aplicado nesta rodada: {len(mud)} imagens da 2ª fonte | com rótulo humano no total: "
           f"{sum(1 for r in inv if r.get('dataset', '').startswith('cristian') and r.get('fonte_fogo') in ('revisao_humana', 'decisao_humana'))} de 400",
           f"  mudou o ambiente: {n_amb} | a fumaça: {n_fum} | o fogo: {n_fogo} | mudam de pasta: {n_mov}",
           f"  pendências (fogo 'incerto', mantido o da IA): {len(pend)} (pendencias.csv)", "",
           "Dataset combinado ANTES (com fogo / sem fogo):"] + tabela(antes) + \
          ["", "Dataset combinado DEPOIS:"] + tabela(inv) + \
          ["", "Para levar ao disco: python scripts/10i_aplicar_rotulos_humanos.py --mover",
           "Depois: rodar de novo a Etapa 11 (estratos.csv com os ambientes novos)."]
    (out / "resumo.txt").write_text("\n".join(txt) + "\n", encoding="utf-8")
    print("\n".join(txt))


if __name__ == "__main__":
    main()
