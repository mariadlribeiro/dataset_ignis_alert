#!/usr/bin/env python3
"""
Etapa 4b - Página para conferir os PARES PARECIDOS entre grupos diferentes (SOMENTE LEITURA).

O 04_divisao.py lista em pares_candidatos.csv TODOS os pares com dHash próximo (Hamming <= 8) que estão em
grupos diferentes, no mesmo split ou não. Conferir todos (e não só os que caíram em splits diferentes)
garante que uma nova divisão nunca crie um par sem veredito. Cada par pode ser a mesma cena (risco de
vazamento) ou falso positivo do hash.
Esta página mostra cada par lado a lado para você decidir:
  * mesma_cena       -> o 04_divisao.py passa a manter as duas imagens no mesmo split;
  * cenas_diferentes -> o par fica registrado como falso positivo e deixa de contar como aviso.

Saída: o botão "Exportar CSV" baixa pares_revisados.csv; guarde em relatorios/04_divisao/ e rode o 04 de novo.
Se pares_revisados.csv já existir, os vereditos dados antes entram na página e são exportados de novo
(inclusive os de pares que já não estão em splits diferentes), então nenhuma decisão se perde entre rodadas.
Abra relatorios/04_divisao/pares.html no Chrome ou Edge. Nada no dataset é alterado.

Uso:  python scripts/04b_pagina_pares.py
"""
import argparse, csv, json
from pathlib import Path

HTML = r"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>Pares parecidos – Ignis Alert</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{--papel:#f3f4f1;--folha:#fff;--tinta:#1e2421;--mudo:#5f6862;--linha:#d5d9d3;--linha2:#e6e9e4;--brasa:#b93d0f;--mata:#2d6a4a;--ambar:#9a5b00;--foco:#1f5fbf;--palco:#1a1d1b}
@media (prefers-color-scheme:dark){:root{--papel:#151816;--folha:#1d211f;--tinta:#e9ece8;--mudo:#9aa39d;--linha:#343a36;--linha2:#2a2f2c;--brasa:#f0844f;--mata:#6cc596;--ambar:#f2b44d;--foco:#7fb0ff;--palco:#0e100f}}
*{box-sizing:border-box}
body{margin:0;background:var(--papel);color:var(--tinta);font:14px/1.45 "Segoe UI Variable Text","Segoe UI",system-ui,sans-serif;font-variant-numeric:tabular-nums}
:focus-visible{outline:2px solid var(--foco);outline-offset:2px}
header{position:sticky;top:0;z-index:5;display:flex;gap:14px;align-items:center;flex-wrap:wrap;padding:10px 18px;background:var(--folha);border-bottom:1px solid var(--linha)}
header b{font-size:15px} .sp{flex:1}
button{font:inherit;color:inherit;cursor:pointer;background:var(--folha);border:1px solid var(--linha);border-radius:6px;padding:6px 12px}
button:hover{border-color:var(--tinta)} button.forte{background:var(--brasa);border-color:var(--brasa);color:#fff;font-weight:600}
main{max-width:1200px;margin:0 auto;padding:14px 18px 40px}
.intro{color:var(--mudo);max-width:80ch;margin:4px 0 16px}
.par{background:var(--folha);border:1px solid var(--linha);border-radius:10px;padding:12px 14px;margin-bottom:14px}
.par.mesma{border-left:5px solid var(--brasa)} .par.dif{border-left:5px solid var(--mata)}
.cab{display:flex;gap:12px;align-items:baseline;margin-bottom:8px;flex-wrap:wrap}
.cab h2{margin:0;font-size:15px} .cab span{color:var(--mudo);font-size:13px}
.lado{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media (max-width:760px){.lado{grid-template-columns:1fr}}
.img{background:var(--palco);border-radius:8px;height:300px;display:flex;align-items:center;justify-content:center;overflow:hidden}
.img img{max-width:100%;max-height:100%;object-fit:contain;cursor:zoom-in}
.leg{font-size:12.5px;color:var(--mudo);margin-top:5px;word-break:break-all}.leg b{color:var(--tinta)}
.acoes{display:flex;gap:8px;margin-top:10px;align-items:center;flex-wrap:wrap}
.acoes button.on.m{background:var(--brasa);border-color:var(--brasa);color:#fff;font-weight:600}
.acoes button.on.d{background:var(--mata);border-color:var(--mata);color:#fff;font-weight:600}
.acoes input{flex:1;min-width:200px;font:inherit;color:inherit;background:var(--folha);border:1px solid var(--linha);border-radius:6px;padding:6px 8px}
#toast{position:fixed;bottom:18px;left:50%;transform:translateX(-50%);background:var(--tinta);color:var(--folha);padding:8px 16px;border-radius:6px;opacity:0;transition:opacity .2s;pointer-events:none}
#toast.on{opacity:1}
</style></head><body>
<header><b>Pares parecidos entre grupos diferentes</b><span id="prog"></span><span class="sp"></span>
 <button id="imp">Importar</button><button id="exp" class="forte">Exportar CSV</button><input id="arq" type="file" accept=".csv" hidden></header>
<main>
<p class="intro">O hash achou estes pares parecidos em grupos diferentes. Os que ainda não têm veredito aparecem primeiro. Se forem a <b>mesma cena</b> (mesmo lugar e momento, mesmo com recorte, zoom ou cor diferentes), o modelo veria no teste algo que já viu no treino. Marque cada par; na dúvida, prefira <b>mesma cena</b>, que é o lado seguro.</p>
<div id="lista"></div>
</main>
<div id="toast" role="status"></div>
<script>
const PARES = __PARES__.map((p,i) => Object.assign(p, {i}));
const ANTERIORES = __ANTERIORES__;
const KEY = 'ignis_pares_v2';   // v2: chave do par independe da ordem; os vereditos vêm do CSV
let st = {}; try { st = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch(e) {}
for (const [k, x] of Object.entries(ANTERIORES)) if (!(st[k] && st[k].v)) st[k] = x;   // o arquivo completa o navegador
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const chave = p => [p.a, p.b].sort().join('||');   // a ordem do par não importa
const salvar = () => { try { localStorage.setItem(KEY, JSON.stringify(st)); } catch(e) {} };
function toast(t){ const e=$('toast'); e.textContent=t; e.className='on'; clearTimeout(toast.t); toast.t=setTimeout(()=>e.className='',1800); }
const nome = c => c.split(/[\\/]/).pop();
function lado(c, s, r){ return `<div><div class="img"><img src="${r.url}" alt="${esc(nome(c))}" loading="lazy" onclick="window.open(this.src,'_blank')"></div>
  <div class="leg"><b>${esc(nome(c))}</b>: split <b>${s}</b>, ${esc(r.ambiente)}, fogo ${esc(r.fogo)}, grupo ${esc(r.grupo)}</div></div>`; }
function render(){
  const n = PARES.filter(p => (st[chave(p)]||{}).v).length;
  const antigos = Object.keys(st).filter(k => st[k].v && !PARES.some(p => chave(p) === k)).length;
  $('prog').textContent = `${n} de ${PARES.length} pares atuais decididos` + (antigos ? ` · ${antigos} decididos em rodadas anteriores (mantidos no CSV)` : '');
  const ordem = PARES.slice().sort((p,q) => (!!(st[chave(p)]||{}).v - !!(st[chave(q)]||{}).v) || (p.i - q.i));
  if (!render.ordem) render.ordem = ordem;            // a ordem fica fixa enquanto a página está aberta
  $('lista').innerHTML = render.ordem.map(p => { const i = p.i, x = st[chave(p)] || {};
    return `<section class="par ${x.v==='mesma_cena'?'mesma':x.v==='cenas_diferentes'?'dif':''}">
     <div class="cab"><h2>Par ${i+1}</h2><span>distância do hash ${p.h} (0 = idênticas; limite do grupo = 6) · ${p.sa===p.sb ? 'mesmo split hoje' : 'splits diferentes hoje'}</span></div>
     <div class="lado">${lado(p.a, p.sa, p.ra)}${lado(p.b, p.sb, p.rb)}</div>
     <div class="acoes"><button class="m ${x.v==='mesma_cena'?'on':''}" data-i="${i}" data-v="mesma_cena">Mesma cena</button>
      <button class="d ${x.v==='cenas_diferentes'?'on':''}" data-i="${i}" data-v="cenas_diferentes">Cenas diferentes</button>
      <input data-i="${i}" placeholder="observação (opcional)" value="${esc(x.o||'')}"></div></section>`; }).join('');
  document.querySelectorAll('.acoes button').forEach(b => b.onclick = () => { const p = PARES[+b.dataset.i], k = chave(p);
    st[k] = Object.assign(st[k]||{}, {v: (st[k]||{}).v === b.dataset.v ? '' : b.dataset.v}); salvar(); render(); });
  document.querySelectorAll('.acoes input').forEach(e => e.oninput = () => { const k = chave(PARES[+e.dataset.i]);
    st[k] = Object.assign(st[k]||{}, {o: e.value}); salvar(); });
}
const q = s => '"' + String(s ?? '').replace(/"/g,'""') + '"';
$('exp').onclick = () => {
  const atuais = new Set(PARES.map(chave));
  const linhas = PARES.map(p => { const x = st[chave(p)] || {}; return [p.a,p.b,p.h,x.v||'',x.o||''].map(q).join(','); })
    .concat(Object.entries(st).filter(([k,x]) => x.v && !atuais.has(k))
      .map(([k,x]) => { const [a,b] = k.split('||'); return [a,b,x.h??'',x.v,x.o||''].map(q).join(','); }));
  const blob = new Blob(['imagem_a,imagem_b,hamming,veredito,observacao\r\n' + linhas.join('\r\n') + '\r\n'], {type:'text/csv;charset=utf-8'});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'pares_revisados.csv';
  document.body.appendChild(a); a.click(); a.remove(); toast('pares_revisados.csv exportado. Guarde em relatorios/04_divisao/');
};
function parseCSV(t){ const out=[]; let row=[], cur='', qq=false;
  for (let i=0;i<t.length;i++){ const ch=t[i];
    if (qq){ if (ch==='"'){ if (t[i+1]==='"'){cur+='"';i++;} else qq=false; } else cur+=ch; }
    else if (ch==='"') qq=true; else if (ch===','){row.push(cur);cur='';} else if (ch==='\n'){row.push(cur);out.push(row);row=[];cur='';} else if (ch!=='\r') cur+=ch; }
  if (cur||row.length){row.push(cur);out.push(row);} return out; }
$('imp').onclick = () => $('arq').click();
$('arq').onchange = async e => { const f = e.target.files[0]; if (!f) return;
  const t = parseCSV((await f.text()).replace(/^﻿/,'')); const h = t.shift(); const ix = n => h.indexOf(n); let c = 0;
  for (const l of t){ if (!l[ix('imagem_a')]) continue; st[chave({a: l[ix('imagem_a')], b: l[ix('imagem_b')]})] = {v: l[ix('veredito')]||'', o: l[ix('observacao')]||'', h: l[ix('hamming')]||''}; c++; }
  salvar(); render(); toast(c + ' pares importados'); e.target.value = ''; };
render();
</script></body></html>
"""


def ler(caminho):
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--origem", default="relatorios/01_origem/origem.json")
    ap.add_argument("--pares", default="relatorios/04_divisao/pares_candidatos.csv",
                    help="padrão: pares_candidatos.csv (todos); se não existir, usa pares_proximos_entre_splits.csv")
    ap.add_argument("--rotulos", default="relatorios/05_consolidacao/rotulos.csv")
    ap.add_argument("--revisados", default="relatorios/04_divisao/pares_revisados.csv")
    ap.add_argument("--saida", default="relatorios/04_divisao/pares.html")
    a = ap.parse_args()

    if not Path(a.pares).exists():
        a.pares = "relatorios/04_divisao/pares_proximos_entre_splits.csv"
    raiz = Path(json.loads(Path(a.origem).read_text(encoding="utf-8"))["caminho_local"])
    rot = {r["caminho_relativo"]: r for r in ler(a.rotulos)} if Path(a.rotulos).exists() else {}
    info = lambda c: {"url": (raiz / c).as_uri(), "ambiente": rot.get(c, {}).get("ambiente", "?"),
                      "fogo": rot.get(c, {}).get("fogo", "?"), "grupo": rot.get(c, {}).get("id_grupo", "?")}
    pares = [{"a": p["imagem_a"], "b": p["imagem_b"], "sa": p["split_a"], "sb": p["split_b"], "h": int(p["hamming"]),
              "ra": info(p["imagem_a"]), "rb": info(p["imagem_b"])} for p in ler(a.pares)]
    chave = lambda x, y: "||".join(sorted((x, y)))       # a ordem do par não importa
    hamming = {chave(p["a"], p["b"]): p["h"] for p in pares}
    anteriores, conflitos = {}, []
    if Path(a.revisados).exists():
        for r in ler(a.revisados):
            if r.get("veredito"):
                k = chave(r["imagem_a"], r["imagem_b"])
                if k in anteriores and anteriores[k]["v"] != r["veredito"]:
                    conflitos.append(k)
                anteriores[k] = {"v": r["veredito"], "o": r.get("observacao", ""), "h": r.get("hamming") or hamming.get(k, "")}
    for k in conflitos:
        print(f"ATENÇÃO: veredito conflitante para o mesmo par (vale o último; confira na página): {k}")
    js = lambda o: json.dumps(o, ensure_ascii=False).replace("</", "<\\/")
    Path(a.saida).write_text(HTML.replace("__PARES__", js(pares)).replace("__ANTERIORES__", js(anteriores)),
                             encoding="utf-8")
    sem = sum(1 for p in pares if chave(p["a"], p["b"]) not in anteriores)
    print(f"Página gerada: {a.saida} | pares ({Path(a.pares).name}): {len(pares)} (sem veredito: {sem}) | "
          f"vereditos anteriores carregados: {len(anteriores)}")
    print("Abra no Chrome ou Edge; exporte pares_revisados.csv para relatorios/04_divisao/ e rode o 04 de novo.")


if __name__ == "__main__":
    main()
