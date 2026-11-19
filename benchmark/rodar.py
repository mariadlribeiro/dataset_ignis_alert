#!/usr/bin/env python3
"""
Benchmark parametrizável do Ignis Alert (LEAS 2026/2).

Cada arquivo em benchmark/campanhas/*.toml descreve uma CAMPANHA: um conjunto de rodadas com parâmetros.
Quem usa escolhe a campanha; o runner monta as rodadas, reaproveita as que já existem e gera o relatório.

Uso:
  python benchmark/rodar.py --listar                      lista as campanhas e quanto de cada uma já foi feito
  python benchmark/rodar.py --campanha redes --so-plano   mostra o que vai rodar e o tempo estimado, sem rodar
  python benchmark/rodar.py --campanha redes              roda o que falta e gera benchmark/resultados/redes/
  python benchmark/rodar.py --campanha redes --refazer    roda tudo de novo (sobrescreve as rodadas da campanha)

Tipos de campanha:
  treino  -> cada rodada chama scripts/12_treinar.py; o resultado fica em relatorios/12_treino/<id>
  atalho  -> chama scripts/13b_avaliar_atalho.py com as redes já treinadas
  custo   -> mede tempo por imagem, parâmetros e tamanho do arquivo de cada rede (nada é treinado)

Regra do teste: a comparação entre rodadas usa a VALIDAÇÃO. O teste aparece na tabela só para registro;
escolher configuração olhando o teste faria dele mais uma validação.
"""
import argparse, csv, itertools, json, os, statistics, subprocess, sys, time, tomllib
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BENCH = RAIZ / "benchmark"
TREINOS = RAIZ / "relatorios" / "12_treino"
PY = sys.executable

# padrões do scripts/12_treinar.py: uma rodada com esses valores tem o mesmo id da Etapa 12
PADRAO = {"aumento": "torchvision", "epocas": 20, "lote": 8, "lr": 0.0001, "paciencia": 7,
          "tamanho": 224, "semente": 42, "teste_rapido": False}
ABREV = {"epocas": "e", "lote": "b", "lr": "lr", "paciencia": "p", "tamanho": "t", "semente": "s"}
MIN_POR_EPOCA = {"resnet18": 2.5, "densenet121": 6.0, "efficientnet_b0": 2.7}   # CPU das autoras; usado se não houver histórico

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass


# ------------------------------------------------------------------ campanhas
def carregar_campanhas():
    camp = {}
    for p in sorted((BENCH / "campanhas").glob("*.toml")):
        with p.open("rb") as f:
            c = tomllib.load(f)
        c["_arquivo"] = p.relative_to(RAIZ).as_posix()
        camp[c["nome"]] = c
    return camp


def id_rodada(r):
    nome = f"{r['rede']}_{r['aumento']}"
    for k, ab in ABREV.items():
        if r[k] != PADRAO[k]:
            nome += f"_{ab}{r[k]}"
    return nome + ("_rapido" if r["teste_rapido"] else "")


def rodadas_treino(c):
    base = {**PADRAO, **c.get("base", {})}
    grade = c.get("grade", {})
    if "rede" not in grade and "rede" not in base:
        sys.exit(f"[ERRO] campanha {c['nome']}: falta 'rede' em [base] ou [grade]")
    chaves = list(grade)
    saida = []
    for valores in itertools.product(*(grade[k] for k in chaves)):
        r = {**base, **dict(zip(chaves, valores))}
        desconhecidas = set(r) - set(PADRAO) - {"rede"}
        if desconhecidas:
            sys.exit(f"[ERRO] campanha {c['nome']}: parâmetro desconhecido {sorted(desconhecidas)}")
        r["id"] = id_rodada(r)
        saida.append(r)
    return saida


def situacao(r):
    """'feita' (mesmos parâmetros), 'conflito' (id igual, parâmetros diferentes) ou 'falta'."""
    pasta = TREINOS / r["id"]
    if not (pasta / "metricas_teste.json").exists() or not (pasta / "config.json").exists():
        return "falta"
    cfg = json.loads((pasta / "config.json").read_text(encoding="utf-8"))
    for k in ("rede", "aumento", "lote", "lr", "paciencia", "tamanho", "semente", "teste_rapido"):
        if cfg.get(k) != r[k] and not (isinstance(r[k], float) and abs(cfg.get(k, 0) - r[k]) < 1e-12):
            return "conflito"
    if not r["teste_rapido"] and cfg.get("epocas") != r["epocas"]:
        return "conflito"
    return "feita"


def estimar_min(r):
    if r["teste_rapido"]:
        return 1.0
    segs = []
    for h in TREINOS.glob(f"{r['rede']}_*/historico.csv"):
        if "_rapido" in h.parent.name:
            continue
        segs += [float(x["segundos"]) for x in csv.DictReader(h.open(encoding="utf-8")) if float(x["segundos"]) < 1500]
    por_epoca = statistics.median(segs) / 60 if segs else MIN_POR_EPOCA.get(r["rede"], 4.0)
    return por_epoca * r["epocas"]


# ------------------------------------------------------------------ execução
def executar(cmd, log):
    log.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    with log.open("w", encoding="utf-8") as f:
        f.write("$ " + " ".join(map(str, cmd)) + "\n")
        p = subprocess.Popen(cmd, cwd=RAIZ, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
        for linha in iter(p.stdout.readline, b""):
            t = linha.decode("utf-8", errors="replace")
            print("   " + t, end="", flush=True); f.write(t)
        return p.wait()


def rodar_treino(c, rodadas, refazer, so_plano):
    total = 0.0
    print(f"\nCampanha {c['nome']}: {c['descricao']}\nArquivo: {c['_arquivo']}\n")
    plano = []
    for r in rodadas:
        st = "falta" if refazer else situacao(r)
        est = estimar_min(r) if st != "feita" else 0.0
        total += est
        plano.append((r, st, est))
        extra = "  (até)" if st != "feita" and not r["teste_rapido"] else ""
        print(f"  {r['id']:42s} {'reaproveitar' if st == 'feita' else st:13s} {est:6.0f} min{extra}")
    print(f"\n  Tempo estimado: até {total:.0f} min (a parada antecipada costuma encurtar).")
    if any(st == "conflito" for _, st, _ in plano):
        sys.exit("\n[PARADO] Há rodada com o mesmo nome e parâmetros diferentes em relatorios/12_treino. "
                 "Use --refazer para sobrescrever ou mude os parâmetros.")
    if so_plano:
        return
    for i, (r, st, est) in enumerate(plano, 1):
        if st == "feita":
            continue
        print(f"\n[{i}/{len(plano)}] {r['id']} (estimado {est:.0f} min)")
        cmd = [PY, "scripts/12_treinar.py", "--rede", r["rede"], "--nome", r["id"], "--aumento", r["aumento"],
               "--epocas", str(r["epocas"]), "--lote", str(r["lote"]), "--lr", str(r["lr"]),
               "--paciencia", str(r["paciencia"]), "--tamanho", str(r["tamanho"]), "--semente", str(r["semente"]),
               "--sobrescrever"]
        if r["teste_rapido"]:
            cmd.append("--teste-rapido")
        if executar(cmd, BENCH / "resultados" / c["nome"] / "logs" / f"{r['id']}.txt") != 0:
            sys.exit(f"[ERRO] a rodada {r['id']} falhou; veja o log em benchmark/resultados/{c['nome']}/logs/")
    relatorio_treino(c, rodadas)


def relatorio_treino(c, rodadas):
    sai = BENCH / "resultados" / c["nome"]; sai.mkdir(parents=True, exist_ok=True)
    linhas = []
    for r in rodadas:
        p = TREINOS / r["id"]
        cfg = json.loads((p / "config.json").read_text(encoding="utf-8"))
        v = json.loads((p / "metricas_validacao.json").read_text(encoding="utf-8"))
        t = json.loads((p / "metricas_teste.json").read_text(encoding="utf-8"))
        hist = list(csv.DictReader((p / "historico.csv").open(encoding="utf-8")))
        segs = [float(h["segundos"]) for h in hist]
        linhas.append({"id": r["id"], "rede": r["rede"], "aumento": r["aumento"], "semente": r["semente"],
                       "epocas_rodadas": cfg["epocas_rodadas"], "melhor_epoca": cfg["melhor_epoca"],
                       "limiar": cfg["limiar_calibrado_na_validacao"],
                       "f2_val": round(v["f2_fogo"], 4), "recall_val": round(v["recall_fogo"], 4),
                       "espec_val": round(v["especificidade"], 4),
                       "f2_teste": round(t["f2_fogo"], 4), "recall_teste": round(t["recall_fogo"], 4),
                       "espec_teste": round(t["especificidade"], 4), "fn_teste": t["fn"], "fp_teste": t["fp"],
                       "min_por_epoca": round(statistics.median(segs) / 60, 2),
                       "concluido_em": cfg["concluido_em"]})
    linhas.sort(key=lambda x: (-x["f2_val"], x["min_por_epoca"]))
    with (sai / "tabela.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0])); w.writeheader(); w.writerows(linhas)

    pct = lambda x: f"{x * 100:.1f}%".replace(".", ",")
    md = [f"# Campanha `{c['nome']}`", "", c["descricao"], "",
          f"Gerado em {datetime.now(timezone.utc).isoformat(timespec='seconds')} a partir de `{c['_arquivo']}`.", "",
          "Ordenado pelo **F2 na validação** (o critério de escolha). As colunas de teste são só registro.", "",
          "| Rodada | F2 val. | Recall val. | Espec. val. | F2 teste | Fogo perdido / alarme falso (teste) | Épocas (melhor) | min/época |",
          "|---|---|---|---|---|---|---|---|"]
    for x in linhas:
        md.append(f"| `{x['id']}` | **{pct(x['f2_val'])}** | {pct(x['recall_val'])} | {pct(x['espec_val'])} | {pct(x['f2_teste'])} "
                  f"| {x['fn_teste']} / {x['fp_teste']} | {x['epocas_rodadas']} ({x['melhor_epoca']}) | {str(round(x["min_por_epoca"], 1)).replace(".", ",")} |")
    if len(linhas) > 1:
        f2v = [x["f2_val"] for x in linhas]; f2t = [x["f2_teste"] for x in linhas]
        md += ["", f"Variação entre as rodadas: F2 na validação de {pct(min(f2v))} a {pct(max(f2v))}; "
                   f"no teste, de {pct(min(f2t))} a {pct(max(f2t))}."]
        if len({x["rede"] for x in linhas}) == 1 and len({x["aumento"] for x in linhas}) == 1:
            md += [f"Só a semente muda: média do F2 no teste {pct(statistics.mean(f2t))}, "
                   f"desvio-padrão {statistics.stdev(f2t) * 100:.2f} pontos. Diferenças entre redes menores que isso "
                   "não indicam que uma é melhor."]
    if any(x["id"].endswith("_rapido") for x in linhas):
        md += ["", "> Teste rápido: 1 época e 40 imagens por conjunto. Os números não têm valor."]
    rapido = any(x["id"].endswith("_rapido") for x in linhas)
    md += ["", ("Validação e teste: 40 imagens cada (amostra do teste rápido)." if rapido else
                "Validação: 210 imagens. Teste: 207 imagens.") + " Métricas com o limiar calibrado na validação.",
           "Arquivos de cada rodada: `relatorios/12_treino/<rodada>/`."]
    (sai / "relatorio.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    grafico(linhas, sai / "grafico.png", c["nome"])
    print("\n" + "\n".join(md[8:]))
    print(f"\n[OK] benchmark/resultados/{c['nome']}/ (tabela.csv, relatorio.md, grafico.png)")


def grafico(linhas, destino, nome):
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    except Exception as e:
        print("(gráfico não gerado:", e, ")"); return
    ids = [x["id"] for x in linhas][::-1]
    fig, ax = plt.subplots(figsize=(8, 0.55 * len(ids) + 1.4))
    y = range(len(ids))
    ax.scatter([x["f2_val"] for x in linhas][::-1], y, s=70, color="#e2591f", label="F2 validação (critério)", zorder=3)
    ax.scatter([x["f2_teste"] for x in linhas][::-1], y, s=70, facecolors="none", edgecolors="#0f2c23", label="F2 teste (registro)", zorder=3)
    ax.set_yticks(list(y)); ax.set_yticklabels(ids)
    lo = min(min(x["f2_val"], x["f2_teste"]) for x in linhas)
    ax.set_xlim(max(0.0, lo - 0.03), 1.005); ax.grid(axis="x", alpha=.3)
    ax.set_xlabel("F2 da classe fogo"); ax.set_title(f"Campanha {nome}")
    ax.legend(loc="lower left", fontsize=8, frameon=False)
    fig.tight_layout(); fig.savefig(destino, dpi=130); plt.close(fig)


def rodar_atalho(c, so_plano):
    p = c["parametros"]
    print(f"\nCampanha {c['nome']}: {c['descricao']}\n  redes: {', '.join(p['redes'])} | rótulos: {p['revisao']}")
    falta = [r for r in p["redes"] if not (RAIZ / "data/modelos" / f"{r}_{p['sufixo']}" / "modelo.pth").exists()]
    if falta:
        print(f"  [atenção] sem pesos treinados para: {', '.join(falta)} (rode antes a campanha redes)")
    print("  Tempo estimado: ~3 min")
    if so_plano:
        return
    sai = BENCH / "resultados" / c["nome"]
    cmd = [PY, "scripts/13b_avaliar_atalho.py", "--revisao", p["revisao"], "--sufixo", p["sufixo"], "--redes", *p["redes"]]
    if executar(cmd, sai / "logs" / "13b.txt") != 0:
        sys.exit("[ERRO] a avaliação de atalho falhou; veja o log.")
    met = list(csv.DictReader((RAIZ / "relatorios/13_atalho/resultado/metricas.csv").open(encoding="utf-8")))
    sai.mkdir(parents=True, exist_ok=True)
    with (sai / "tabela.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(met[0])); w.writeheader(); w.writerows(met)
    pct = lambda x: f"{float(x) * 100:.1f}%".replace(".", ",")
    md = [f"# Campanha `{c['nome']}`", "", c["descricao"], "",
          "| Rede | Recall teste → atalho | Especificidade teste → atalho | Fogo perdido / alarme falso (atalho) |", "|---|---|---|---|"]
    md += [f"| {m['rede']} | {pct(m['recall_fogo_teste'])} → **{pct(m['recall_fogo_atalho'])}** | "
           f"{pct(m['especificidade_teste'])} → {pct(m['especificidade_atalho'])} | {m['fn_atalho']} / {m['fp_atalho']} |" for m in met]
    md += ["", "Uma queda grande no recall indicaria que a rede usa o formato da imagem em vez da chama.",
           "Detalhes: `relatorios/13_atalho/resultado/`."]
    (sai / "relatorio.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n" + "\n".join(md[4:]) + f"\n\n[OK] benchmark/resultados/{c['nome']}/")


def rodar_custo(c, so_plano):
    p = c["parametros"]
    combos = list(itertools.product(p["redes"], p["lote"], p["tamanho"]))
    print(f"\nCampanha {c['nome']}: {c['descricao']}\n  {len(combos)} combinações x {p['repeticoes']} medições | Tempo estimado: ~{max(1, len(combos))} min")
    if so_plano:
        return
    import importlib.util, torch
    spec = importlib.util.spec_from_file_location("treino12", RAIZ / "scripts" / "12_treinar.py")
    t12 = importlib.util.module_from_spec(spec); spec.loader.exec_module(t12)
    if p.get("threads"):
        torch.set_num_threads(int(p["threads"]))
    linhas = []
    for rede, lote, tam in combos:
        m = t12.criar_rede(rede, pre_treinada=False).eval()
        pesos = RAIZ / "data/modelos" / f"{rede}_torchvision" / "modelo.pth"
        if pesos.exists():
            m.load_state_dict(torch.load(pesos, map_location="cpu")["estado"])
        x = torch.randn(lote, 3, tam, tam)
        with torch.no_grad():
            for _ in range(3):
                m(x)
            tempos = []
            for _ in range(p["repeticoes"]):
                t0 = time.perf_counter(); m(x); tempos.append(time.perf_counter() - t0)
        ms = statistics.median(tempos) * 1000 / lote
        linhas.append({"rede": rede, "lote": lote, "tamanho": tam, "ms_por_imagem": round(ms, 2),
                       "imagens_por_segundo": round(1000 / ms, 1),
                       "parametros_milhoes": round(sum(q.numel() for q in m.parameters()) / 1e6, 2),
                       "arquivo_mb": round(pesos.stat().st_size / 2**20, 1) if pesos.exists() else "",
                       "threads": torch.get_num_threads(), "torch": torch.__version__})
        print(f"  {rede:16s} lote {lote:2d} | {tam}px | {ms:7.1f} ms/imagem")
    sai = BENCH / "resultados" / c["nome"]; sai.mkdir(parents=True, exist_ok=True)
    with (sai / "tabela.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0])); w.writeheader(); w.writerows(linhas)
    md = [f"# Campanha `{c['nome']}`", "", c["descricao"], "",
          f"Medido em {datetime.now(timezone.utc).isoformat(timespec='seconds')}, CPU, {linhas[0]['threads']} threads, torch {linhas[0]['torch']}. "
          "Mediana de " + str(p["repeticoes"]) + " medições.", "",
          "| Rede | Lote | Resolução | ms por imagem | Imagens/s | Parâmetros (milhões) | Arquivo (MB) |", "|---|---|---|---|---|---|---|"]
    md += [f"| {x['rede']} | {x['lote']} | {x['tamanho']} | {x['ms_por_imagem']} | {x['imagens_por_segundo']} | "
           f"{x['parametros_milhoes']} | {x['arquivo_mb']} |" for x in linhas]
    md += ["", "O tempo depende da máquina: compare as redes entre si, na mesma máquina, não com outros computadores."]
    (sai / "relatorio.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"\n[OK] benchmark/resultados/{c['nome']}/ (tabela.csv, relatorio.md)")


# ------------------------------------------------------------------ principal
def main():
    ap = argparse.ArgumentParser(description="Benchmark parametrizável do Ignis Alert")
    ap.add_argument("--listar", action="store_true", help="lista as campanhas disponíveis")
    ap.add_argument("--campanha", help="nome da campanha (veja --listar)")
    ap.add_argument("--so-plano", action="store_true", help="mostra o plano e o tempo estimado, sem rodar")
    ap.add_argument("--refazer", action="store_true", help="roda de novo rodadas que já existem")
    a = ap.parse_args()
    camp = carregar_campanhas()

    if a.listar or not a.campanha:
        print("Campanhas disponíveis (benchmark/campanhas/):\n")
        for n, c in camp.items():
            if c["tipo"] == "treino":
                rs = rodadas_treino(c); feitas = sum(situacao(r) == "feita" for r in rs)
                est = sum(estimar_min(r) for r in rs if situacao(r) != "feita")
                st = f"{feitas}/{len(rs)} rodadas feitas" + (f", falta até ~{est:.0f} min" if feitas < len(rs) else "")
            else:
                st = "avaliação, sem treino (minutos)"
            print(f"  {n:10s} [{c['tipo']}] {c['descricao']}\n             {st}")
        print("\nRode:  python benchmark/rodar.py --campanha <nome> [--so-plano]")
        return
    if a.campanha not in camp:
        sys.exit(f"[ERRO] campanha '{a.campanha}' não existe. Disponíveis: {', '.join(camp)}")
    c = camp[a.campanha]
    if c["tipo"] == "treino":
        rodar_treino(c, rodadas_treino(c), a.refazer, a.so_plano)
    elif c["tipo"] == "atalho":
        rodar_atalho(c, a.so_plano)
    elif c["tipo"] == "custo":
        rodar_custo(c, a.so_plano)
    else:
        sys.exit(f"[ERRO] tipo de campanha desconhecido: {c['tipo']}")


if __name__ == "__main__":
    main()
