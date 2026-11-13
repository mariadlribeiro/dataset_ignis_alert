#!/usr/bin/env python3
"""
Etapa 9e - RELATÓRIO VISUAL das condições: um HTML com as imagens agrupadas por cada característica
(SOMENTE LEITURA: lê os originais só para fazer miniaturas na memória; não altera nada).

Para cada característica (iluminação, ponto de vista, distância do fogo, pessoas, veículos, texto,
o que pode confundir, orientação, preto e branco, qualidade JPEG) mostra:
  * quantas imagens têm cada valor, no total e em treino, validação e teste;
  * a porcentagem entre as imagens COM fogo e SEM fogo;
  * até 12 miniaturas sorteadas (semente 42) de cada valor.

E uma tabela de ATALHOS POSSÍVEIS: valores muito mais comuns numa classe do que na outra (ex.: pessoas
em 60% das imagens com fogo e 5% das sem fogo). Um modelo pode aprender esses atalhos em vez do fogo.

O HTML é um arquivo só (as miniaturas vão embutidas), bom para abrir em qualquer computador ou apresentar.

Entradas : relatorios/09_condicoes/condicoes.csv (09d) e medidas_auto.csv (09a); origem.json
Saída    : relatorios/09_condicoes/relatorio_condicoes.html

Uso:  python scripts/09e_relatorio_condicoes.py [--por-valor 12] [--diferenca 20]
"""
import argparse, base64, csv, html, io, json, random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

SPLITS = ("treino", "validacao", "teste")
CARACT = [  # (coluna, título, ordem dos valores, explicação curta)
    ("iluminacao", "Iluminação (medida automática)", ["escura", "media", "clara"], "Brilho médio da imagem: escura < 70 ≤ média < 110 ≤ clara."),
    ("ponto_vista", "Ponto de vista", ["chao", "elevado", "aereo", "satelite", "incerto"], "De onde a foto foi tirada."),
    ("distancia_fogo", "Distância do fogo", ["perto", "medio", "distante", "incerto", "nao_se_aplica"], "Quanto o fogo ocupa da imagem (só imagens com fogo)."),
    ("hora_dia", "Hora do dia", ["dia", "noite", "entardecer", "incerto"], "Que hora do dia parece ser."),
    ("ceu", "Céu visível", ["sim", "nao"], "Se aparece céu na imagem."),
    ("vegetacao", "Vegetação", ["floresta_densa", "campo", "urbana", "sem_vegetacao"], "Que vegetação aparece."),
    ("agua", "Água na cena", ["sim", "nao"], "Rio, lago, mar ou jato de mangueira."),
    ("pessoas", "Pessoas na imagem", ["sim", "nao"], "Bombeiros, moradores, curiosos."),
    ("veiculos", "Veículos na imagem", ["sim", "nao"], "Carro, caminhão, viatura, helicóptero, avião."),
    ("texto", "Texto ou marca d'água", ["sim", "nao"], "Texto, logotipo ou marca d'água sobre a imagem."),
    ("confusor", "O que pode confundir", ["nenhum", "por_do_sol", "luz_artificial", "reflexo", "neblina"], "Algo que parece fogo sem ser, ou que esconde o fogo."),
    ("tipo_fogo", "Tipo de fogo", ["florestal", "estrutura", "veiculo", "campo", "controlado", "outro", "nao_se_aplica"], "Só imagens com fogo."),
    ("focos", "Quantidade de focos", ["um", "varios", "nao_se_aplica"], "Só imagens com fogo."),
    ("cor_chamas", "Cor das chamas", ["amarela", "laranja", "vermelha", "azulada", "mista", "nao_se_aplica"], "Só imagens com fogo."),
    ("encoberto", "Fogo encoberto", ["nao", "fumaca", "vegetacao", "pessoas_objetos", "nao_se_aplica"], "Se algo esconde parte do fogo (só imagens com fogo)."),
    ("orientacao", "Orientação (automática)", ["paisagem", "retrato", "quadrada"], "Proporção da imagem."),
    ("preto_e_branco", "Preto e branco (automático)", ["sim", "nao"], "Saturação média abaixo de 12."),
    ("moldura", "Moldura ou barras (automático)", ["nenhuma", "barras_horizontais", "barras_verticais", "moldura"], "Faixas lisas pretas ou brancas nas bordas."),
    ("blocos_visiveis", "Blocos de compressão visíveis (automático)", ["sim", "nao"], "Quadradinhos do JPEG aparentes."),
    ("faixa_ceu", "Céu na metade de cima (automático)", ["nenhum (< 5%)", "pouco (5-30%)", "muito (30%+)"], "Estimativa pela cor; não conta céu de noite nem coberto de fumaça escura."),
    ("faixa_foco", "Tamanho do maior foco quente (automático)", ["pequeno (< 5%)", "médio (5-25%)", "grande (25%+)", "nao_se_aplica"], "Maior mancha contínua de tons de fogo (só imagens com fogo)."),
    ("faixa_qualidade", "Qualidade JPEG estimada (automática)", ["alta (85+)", "média (60-84)", "baixa (< 60)", "não é JPEG"], "Pelas tabelas de quantização do arquivo."),
]
ROT = {"chao": "do chão", "elevado": "elevado", "aereo": "aéreo", "satelite": "satélite", "incerto": "incerto",
       "perto": "perto", "medio": "médio", "distante": "distante", "nao_se_aplica": "não se aplica",
       "sim": "sim", "nao": "não", "nenhum": "nenhum", "por_do_sol": "pôr do sol", "luz_artificial": "luz artificial",
       "reflexo": "reflexo", "neblina": "neblina", "escura": "escura", "media": "média", "clara": "clara",
       "pendente": "pendente", "barras_horizontais": "barras em cima e embaixo", "barras_verticais": "barras dos lados", "moldura": "moldura", "dia": "dia", "noite": "noite", "entardecer": "entardecer/amanhecer", "floresta_densa": "floresta densa",
       "campo": "campo/cerrado", "urbana": "urbana", "sem_vegetacao": "sem vegetação", "florestal": "florestal", "estrutura": "prédio/casa",
       "veiculo": "veículo", "controlado": "controlado", "outro": "outro", "um": "um foco", "varios": "vários focos", "amarela": "amarela",
       "laranja": "laranja", "vermelha": "vermelha", "azulada": "azulada", "mista": "mista", "fumaca": "por fumaça",
       "vegetacao": "por vegetação", "pessoas_objetos": "por pessoas/objetos", "treino": "treino", "validacao": "validação", "teste": "teste"}

CSS = """
:root{--papel:#f3f4f1;--folha:#fff;--tinta:#1e2421;--mudo:#5f6862;--linha:#d5d9d3;--brasa:#b93d0f;--fogo:#e0531b;--mata:#14875c}
*{box-sizing:border-box}body{margin:0;background:var(--papel);color:var(--tinta);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1180px;margin:0 auto;padding:28px 18px 60px}
h1{font-size:30px;margin:0 0 4px}h2{font-size:22px;margin:0 0 2px}h3{font-size:16px;margin:0}
.sub{color:var(--mudo);margin:0 0 18px}.card{background:var(--folha);border:1px solid var(--linha);border-radius:14px;padding:18px 20px;margin:18px 0}
nav{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0 4px}nav a{font-size:13px;padding:4px 10px;border:1px solid var(--linha);border-radius:99px;color:var(--tinta);text-decoration:none;background:var(--folha)}
table{border-collapse:collapse;width:100%;font-size:13.5px;margin-top:10px}th,td{padding:6px 8px;border-bottom:1px solid var(--linha);text-align:right}
th:first-child,td:first-child{text-align:left}th{color:var(--mudo);font-weight:600}
.barra{display:flex;height:10px;border-radius:5px;overflow:hidden;background:#e7eae5;min-width:120px}.barra i{display:block;height:100%}
.valor{margin-top:16px;border-top:1px solid var(--linha);padding-top:12px}
.valor .cab{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}.valor .cab b{font-size:15px}.valor .cab span{color:var(--mudo);font-size:13px}
.mini{display:flex;gap:6px;overflow-x:auto;margin-top:8px;padding-bottom:4px}
.mini figure{margin:0;flex:0 0 auto}.mini img{height:96px;border-radius:6px;display:block;border-bottom:4px solid var(--linha)}
.mini img.f-sim{border-bottom-color:var(--fogo)}.mini img.f-nao{border-bottom-color:var(--mata)}
.mini figcaption{font-size:11px;color:var(--mudo);max-width:150px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
.alerta{background:#fbe7dc;border-color:#f0c6b0}.ok{color:var(--mata);font-weight:600}.no{color:var(--brasa);font-weight:600}
.leg{display:flex;gap:14px;font-size:13px;color:var(--mudo);margin-top:6px}.leg i{display:inline-block;width:12px;height:12px;border-radius:3px;vertical-align:-1px;margin-right:4px}
"""


def ler(caminho):
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def faixa_q(q):
    if q in ("", None):
        return "não é JPEG"
    q = int(q)
    return "alta (85+)" if q >= 85 else ("média (60-84)" if q >= 60 else "baixa (< 60)")


def miniatura(caminho, altura=96):
    with Image.open(caminho) as im:
        im.seek(0); im = im.convert("RGB")
        im.thumbnail((altura * 3, altura))
        b = io.BytesIO(); im.save(b, "JPEG", quality=72)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


def main():
    ap = argparse.ArgumentParser()
    d = "relatorios/09_condicoes"
    ap.add_argument("--origem", default="relatorios/01_origem/origem.json")
    ap.add_argument("--condicoes", default=f"{d}/condicoes.csv")
    ap.add_argument("--medidas", default=f"{d}/medidas_auto.csv")
    ap.add_argument("--saida", default=f"{d}/relatorio_condicoes.html")
    ap.add_argument("--por-valor", type=int, default=12)
    ap.add_argument("--diferenca", type=float, default=20.0, help="pontos percentuais entre as classes para marcar atalho")
    a = ap.parse_args()

    raiz = Path(json.loads(Path(a.origem).read_text(encoding="utf-8"))["caminho_local"])
    cond = {r["caminho_original"]: r for r in ler(a.condicoes)}
    med = {r["caminho_original"]: r for r in ler(a.medidas)} if Path(a.medidas).exists() else {}
    linhas = []
    for k, r in cond.items():
        m = med.get(k, {})
        l = dict(r)
        for c in ("orientacao", "preto_e_branco"):
            l.setdefault(c, m.get(c, ""))
            if not l[c]: l[c] = m.get(c, "")
        l["faixa_qualidade"] = faixa_q(m.get("jpeg_qualidade_est", "")) if m else ""
        for c in ("moldura", "blocos_visiveis"):
            l[c] = m.get(c, "")
        if m.get("pct_ceu_est", "") != "":
            v = float(m["pct_ceu_est"]); l["faixa_ceu"] = "nenhum (< 5%)" if v < 5 else ("pouco (5-30%)" if v < 30 else "muito (30%+)")
        if m.get("pct_maior_foco", "") != "":
            v = float(m["pct_maior_foco"])
            l["faixa_foco"] = "nao_se_aplica" if l["fogo"] != "sim" else ("pequeno (< 5%)" if v < 5 else ("médio (5-25%)" if v < 25 else "grande (25%+)"))
        linhas.append(l)
    caract = [c for c in CARACT if any(l.get(c[0]) for l in linhas)]
    n_fogo = Counter(l["fogo"] for l in linhas)

    secoes, atalhos, cache = [], [], {}
    rnd = random.Random(42)
    for col, titulo, ordem, expl in caract:
        valores = [v for v in ordem if any(l.get(col) == v for l in linhas)] + sorted({l.get(col, "") for l in linhas} - set(ordem) - {""})
        tab = ["<tr><th>Valor</th><th>Total</th>" + "".join(f"<th>{ROT[s]}</th>" for s in SPLITS) +
               "<th>% das com fogo</th><th>% das sem fogo</th><th></th></tr>"]
        blocos = []
        for v in valores:
            grupo = [l for l in linhas if l.get(col) == v]
            por_split = Counter(l["split"] for l in grupo)
            pf = 100 * sum(l["fogo"] == "sim" for l in grupo) / max(n_fogo["sim"], 1)
            pn = 100 * sum(l["fogo"] == "nao" for l in grupo) / max(n_fogo["nao"], 1)
            aplicavel = col not in ("distancia_fogo", "tipo_fogo", "focos", "cor_chamas", "encoberto", "faixa_foco")
            binario = col in ("pessoas", "veiculos", "texto", "preto_e_branco", "ceu", "agua", "blocos_visiveis")
            if aplicavel and v not in ("incerto", "pendente") and not (binario and v == "nao") and abs(pf - pn) >= a.diferenca:
                atalhos.append((titulo, ROT.get(v, v), pf, pn))
            tab.append(f"<tr><td>{html.escape(ROT.get(v, v))}</td><td>{len(grupo)}</td>" +
                       "".join(f"<td>{por_split[s]}</td>" for s in SPLITS) +
                       f"<td>{pf:.0f}%</td><td>{'—' if not aplicavel else f'{pn:.0f}%'}</td>"
                       f"<td><div class='barra' title='proporção com fogo neste valor'><i style='width:{100 * sum(l['fogo'] == 'sim' for l in grupo) / max(len(grupo), 1):.0f}%;background:var(--fogo)'></i>"
                       f"<i style='flex:1;background:var(--mata)'></i></div></td></tr>")
            amostra = rnd.sample(grupo, min(a.por_valor, len(grupo)))
            figs = []
            for l in amostra:
                k = l["caminho_original"]
                if k not in cache:
                    try:
                        cache[k] = miniatura(raiz / k.replace("\\", "/"))
                    except Exception:
                        cache[k] = ""
                if cache[k]:
                    nome = k.replace("\\", "/").split("/")[-1]
                    figs.append(f"<figure><img class='f-{l['fogo']}' src='{cache[k]}' alt='{html.escape(nome)}' title='{html.escape(nome)} · {ROT.get(l['split'], l['split'])}'>"
                                f"<figcaption>{html.escape(nome)}</figcaption></figure>")
            blocos.append(f"<div class='valor'><div class='cab'><b>{html.escape(ROT.get(v, v))}</b><span>{len(grupo)} imagens</span></div>"
                          f"<div class='mini'>{''.join(figs)}</div></div>")
        secoes.append((col, f"<section class='card' id='{col}'><h2>{html.escape(titulo)}</h2><p class='sub'>{html.escape(expl)}</p>"
                            f"<table>{''.join(tab)}</table>{''.join(blocos)}</section>"))

    if atalhos:
        linhas_at = "".join(f"<tr><td>{html.escape(t)}: <b>{html.escape(v)}</b></td><td>{pf:.0f}%</td><td>{pn:.0f}%</td>"
                            f"<td class='no'>{pf - pn:+.0f} pontos</td></tr>" for t, v, pf, pn in sorted(atalhos, key=lambda x: -abs(x[2] - x[3])))
        bloco_at = (f"<section class='card alerta'><h2>Atalhos possíveis</h2><p class='sub'>Valores com diferença de {a.diferenca:.0f} pontos "
                    f"ou mais entre as imagens com fogo e sem fogo. O modelo pode aprender esses sinais em vez do fogo; vale conferir "
                    f"o erro do modelo nesses grupos e buscar exemplos do outro lado nos próximos datasets.</p>"
                    f"<table><tr><th>Característica</th><th>% das com fogo</th><th>% das sem fogo</th><th>Diferença</th></tr>{linhas_at}</table></section>")
    else:
        bloco_at = "<section class='card'><h2>Atalhos possíveis</h2><p class='ok'>Nenhuma característica com diferença grande entre as classes.</p></section>"

    nav = "".join(f"<a href='#{c}'>{html.escape(t)}</a>" for c, t, _, _ in caract)
    pagina = (f"<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
              f"<title>Condições das imagens – Ignis Alert</title><style>{CSS}</style></head><body><main>"
              f"<h1>Condições das imagens</h1><p class='sub'>{len(linhas)} imagens incluídas na divisão · {n_fogo['sim']} com fogo, {n_fogo['nao']} sem fogo · "
              f"gerado em {datetime.now(timezone.utc).strftime('%d/%m/%Y')}</p>"
              f"<div class='leg'><span><i style='background:var(--fogo)'></i>com fogo</span><span><i style='background:var(--mata)'></i>sem fogo</span>"
              f"<span>(cor na borda de baixo de cada miniatura)</span></div><nav>{nav}</nav>{bloco_at}"
              + "".join(s for _, s in secoes) + "</main></body></html>")
    Path(a.saida).write_text(pagina, encoding="utf-8")
    print(f"Relatório: {a.saida} ({len(pagina) / 1e6:.1f} MB, {len(cache)} miniaturas)")
    print(f"Atalhos possíveis (diferença >= {a.diferenca:.0f} pontos): {len(atalhos)}")
    for t, v, pf, pn in sorted(atalhos, key=lambda x: -abs(x[2] - x[3])):
        print(f"  {t}: {v:16s} com fogo {pf:4.0f}% | sem fogo {pn:4.0f}%")
    print("Nada no dataset foi alterado.")


if __name__ == "__main__":
    main()
