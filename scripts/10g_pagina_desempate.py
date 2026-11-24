#!/usr/bin/env python3
"""
Etapa 10g - PÁGINA DE DESEMPATE das divergências da revisão humana (10f).

Para cada imagem de revisao_humana_A/divergencias.csv mostra, lado a lado, a resposta cega da revisora, o rótulo da
revisão por IA e a anotação que a IA fez, e pede o rótulo FINAL de ambiente, fogo e fumaça. Agora nada é cego:
o objetivo é decidir com calma, olhando a foto grande. A página não decide nada sozinha (nenhum campo vem marcado).

O botão "Exportar CSV" baixa desempate_preenchido.csv (guarde em revisao_humana_A/). Nada no dataset muda aqui:
aplicar as decisões é um passo à parte, registrado em selecao_A/decisoes.csv.

Uso:  python scripts/10g_pagina_desempate.py [--revisora revisora]
"""
import argparse, csv, json, os, re
from pathlib import Path, PureWindowsPath

NOME = "cristiancristancho_forest-fire-image-dataset"
CAMPOS = {
    "ambiente": [("floresta", "Floresta"), ("cidade", "Cidade"), ("casa", "Casa"), ("predios", "Prédios"),
                 ("flores_jardins", "Flores e jardins"), ("outros", "Outros"), ("ambiente_incerto", "Incerto")],
    "fogo": [("sim", "Sim"), ("nao", "Não"), ("incerto", "Incerto")],
    "fumaca": [("sim", "Sim"), ("nao", "Não"), ("incerto", "Incerto")],
}
CRIT = {  # mesmos critérios da página de revisão (05b)
    "ambiente": "Floresta: mata, bosque, vegetação densa ou paisagem florestal vista de longe. Cidade: rua, bairro ou "
                "espaço público urbano. Casa: residência, quintal. Prédios: comercial, industrial, fábrica. "
                "Outros: campo aberto, montanha, lago, veículo, objeto ou pessoa em destaque. "
                "Incerto: não dá para dizer onde é.",
    "fogo": "Sim: chama visível, mesmo pequena. Brilho, céu laranja, brasa sem chama ou só fumaça contam como Não.",
    "fumaca": "Sim: fumaça ou névoa de queima visível. Neblina comum ou nuvem não contam. "
              "Incerto: pode ser fumaça, neblina ou nuvem.",
}

HTML = r"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Desempate – Ignis Alert</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{--papel:#f3f4f1;--folha:#fff;--tinta:#1e2421;--mudo:#5f6862;--linha:#d5d9d3;--brasa:#b93d0f;--mata:#2d6a4a;--mata-s:#dff0e6;--ia:#1f5fbf;--ia-s:#e3edfb;--rev:#9a5b00;--rev-s:#fdf0d5;--palco:#1a1d1b}
@media (prefers-color-scheme:dark){:root{--papel:#151816;--folha:#1d211f;--tinta:#e9ece8;--mudo:#9aa39d;--linha:#343a36;--mata:#6cc596;--mata-s:#1b3327;--ia:#7fb0ff;--ia-s:#18263b;--rev:#f2b44d;--rev-s:#3a2c10;--palco:#0e100f}}
*{box-sizing:border-box}body{margin:0;height:100dvh;display:flex;flex-direction:column;background:var(--papel);color:var(--tinta);font:14px/1.45 "Segoe UI",system-ui,sans-serif}
header{display:flex;gap:14px;align-items:center;padding:8px 16px;background:var(--folha);border-bottom:1px solid var(--linha);flex-wrap:wrap}
header h1{font-size:15px;margin:0}.barra{flex:1;min-width:160px;height:6px;background:var(--linha);border-radius:3px;overflow:hidden}.barra i{display:block;height:100%;background:var(--mata)}
button{font:inherit;padding:6px 12px;border:1px solid var(--linha);border-radius:6px;background:var(--folha);color:var(--tinta);cursor:pointer}
button.pri{background:var(--brasa);border-color:var(--brasa);color:#fff;font-weight:600}
main{flex:1;display:grid;grid-template-columns:1fr 440px;min-height:0}
.palco{background:var(--palco);display:flex;align-items:center;justify-content:center;min-height:0;padding:12px}
.palco img{max-width:100%;max-height:100%;object-fit:contain}
aside{overflow:auto;padding:14px 16px;background:var(--folha);border-left:1px solid var(--linha)}
h2{font-size:16px;margin:0 0 2px}.meta{color:var(--mudo);font-size:12px;margin-bottom:10px;word-break:break-all}
.compara{display:grid;grid-template-columns:auto 1fr 1fr;gap:4px 10px;font-size:13px;margin:8px 0 12px;align-items:center}
.compara b{font-size:12px}.cel{padding:2px 8px;border-radius:5px}.ia{background:var(--ia-s);color:var(--ia)}.rv{background:var(--rev-s);color:var(--rev)}
.dif{outline:2px solid var(--brasa)}.nota{font-size:13px;background:var(--ia-s);padding:6px 10px;border-radius:6px;margin-bottom:12px}
fieldset{border:0;border-top:1px solid var(--linha);padding:10px 0 6px;margin:0}legend{font-weight:600;padding:0}
.crit{color:var(--mudo);font-size:12px;margin:2px 0 6px}.ops{display:flex;flex-wrap:wrap;gap:6px}
.ops button{padding:5px 10px}.ops button.on{background:var(--mata);border-color:var(--mata);color:#fff}
.ops button .tag{font-size:10px;margin-left:4px;opacity:.75}
textarea{width:100%;min-height:52px;font:inherit;padding:6px;border:1px solid var(--linha);border-radius:6px;background:var(--papel);color:var(--tinta)}
.nav{display:flex;gap:8px;margin-top:12px}.nav button{flex:1}.mapa{display:flex;flex-wrap:wrap;gap:3px;margin-top:12px}
.mapa span{width:16px;height:16px;border-radius:3px;background:var(--linha);cursor:pointer}.mapa span.ok{background:var(--mata)}.mapa span.at{outline:2px solid var(--brasa)}
.erro{color:#fff;padding:20px;text-align:center}
@media (max-width:900px){main{grid-template-columns:1fr}.palco{height:50vh}}
</style></head><body>
<header><h1>Desempate · revisão humana × IA</h1><div class="barra"><i id="prog"></i></div><span id="cont"></span>
<button id="exp" class="pri">Exportar CSV</button></header>
<main><div class="palco"><img id="img" alt="Imagem em revisão"></div>
<aside><h2 id="tit"></h2><div class="meta" id="meta"></div>
<div class="compara" id="comp"></div><div class="nota" id="nota"></div>
<div id="campos"></div>
<fieldset><legend>Observação</legend><textarea id="obs" placeholder="Opcional: por que decidiu assim"></textarea></fieldset>
<div class="nav"><button id="ant">← Anterior</button><button id="prox">Próxima →</button></div>
<div class="mapa" id="mapa"></div>
<p class="meta" style="margin-top:10px">Teclas: ← → navegam. A decisão fica salva no navegador até você exportar.</p></aside></main>
<script>
const DATA = __DATA__, CAMPOS = __CAMPOS__, CRIT = __CRIT__, CHAVE = __CHAVE__, EXPORTAR = __EXPORTAR__;
const $ = id => document.getElementById(id);
let est = {}; try { est = JSON.parse(localStorage.getItem(CHAVE) || '{}'); } catch (e) {}
const salvar = () => { try { localStorage.setItem(CHAVE, JSON.stringify(est)); } catch (e) {} };
let i = 0;
const reg = r => est[r.n] || (est[r.n] = {});
const feito = r => Object.keys(CAMPOS).every(c => reg(r)[c]);
const nomeOp = (c, v) => (CAMPOS[c].find(o => o[0] === v) || [v, v || '—'])[1];
function mostrar() {
  const r = DATA[i], x = reg(r);
  $('img').src = r.url; $('img').onerror = () => { $('img').replaceWith(Object.assign(document.createElement('div'), {className:'erro', id:'img', textContent:'Não consegui abrir a imagem: ' + r.caminho})); };
  if ($('img').tagName !== 'IMG') { const im = document.createElement('img'); im.id = 'img'; $('img').replaceWith(im); im.src = r.url; }
  $('tit').textContent = `Imagem nº ${r.n} · ${i + 1} de ${DATA.length}`;
  $('meta').textContent = `${r.caminho} · ${r.split} · diverge em: ${r.diverge.replace(/\+/g, ', ')}`;
  let h = '<span></span><b>Você (às cegas)</b><b>Revisão por IA</b>';
  for (const c of Object.keys(CAMPOS)) { const d = r.rev[c] !== r.ia[c] ? ' dif' : '';
    h += `<b>${c === 'fumaca' ? 'fumaça' : c}</b><span class="cel rv${d}">${nomeOp(c, r.rev[c])}</span><span class="cel ia${d}">${nomeOp(c, r.ia[c])}</span>`; }
  $('comp').innerHTML = h;
  $('nota').innerHTML = r.nota_ia ? '<b>Anotação da IA:</b> ' + r.nota_ia.replace(/</g, '&lt;') : '<b>Anotação da IA:</b> nenhuma';
  $('campos').innerHTML = Object.keys(CAMPOS).map(c => `<fieldset><legend>${c === 'fumaca' ? 'Fumaça' : c[0].toUpperCase() + c.slice(1)} final</legend>
    <div class="crit">${CRIT[c]}</div><div class="ops">${CAMPOS[c].map(([v, t]) => `<button data-c="${c}" data-v="${v}" class="${x[c] === v ? 'on' : ''}">${t}${v === r.rev[c] ? '<span class="tag">você</span>' : ''}${v === r.ia[c] ? '<span class="tag">IA</span>' : ''}</button>`).join('')}</div></fieldset>`).join('');
  $('obs').value = x.obs || '';
  const n = DATA.filter(feito).length; $('cont').textContent = `${n} de ${DATA.length} decididas`; $('prog').style.width = (100 * n / DATA.length) + '%';
  $('mapa').innerHTML = DATA.map((d, k) => `<span title="nº ${d.n}" data-k="${k}" class="${feito(d) ? 'ok' : ''} ${k === i ? 'at' : ''}"></span>`).join('');
}
$('campos').onclick = e => { const b = e.target.closest('button'); if (!b) return; reg(DATA[i])[b.dataset.c] = b.dataset.v; salvar(); mostrar(); };
$('obs').oninput = () => { reg(DATA[i]).obs = $('obs').value; salvar(); };
$('mapa').onclick = e => { if (e.target.dataset.k) { i = +e.target.dataset.k; mostrar(); } };
$('ant').onclick = () => { i = (i - 1 + DATA.length) % DATA.length; mostrar(); };
$('prox').onclick = () => { i = (i + 1) % DATA.length; mostrar(); };
document.onkeydown = e => { if (e.target.tagName === 'TEXTAREA') return; if (e.key === 'ArrowLeft') $('ant').click(); if (e.key === 'ArrowRight') $('prox').click(); };
const q = s => '"' + String(s ?? '').replace(/"/g, '""') + '"';
$('exp').onclick = () => {
  const cols = ['n','caminho_relativo','split','diverge_em','ambiente_ia','fogo_ia','fumaca_ia','ambiente_revisora','fogo_revisora','fumaca_revisora','ambiente_final','fogo_final','fumaca_final','observacao','decidida'];
  const lin = DATA.map(r => { const x = reg(r); return [r.n, r.caminho, r.split, r.diverge, r.ia.ambiente, r.ia.fogo, r.ia.fumaca, r.rev.ambiente, r.rev.fogo, r.rev.fumaca,
    x.ambiente, x.fogo, x.fumaca, x.obs, feito(r) ? 'sim' : 'nao'].map(q).join(','); });
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([cols.join(',') + '\r\n' + lin.join('\r\n') + '\r\n'], {type:'text/csv;charset=utf-8'}));
  a.download = EXPORTAR; document.body.appendChild(a); a.click(); a.remove();
};
mostrar();
</script></body></html>"""


def ler(caminho):
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main():
    pasta = Path("relatorios/10_nova_fonte") / NOME
    ap = argparse.ArgumentParser()
    ap.add_argument("--pasta", default=str(pasta / "revisao_humana_A"))
    ap.add_argument("--selecao", default=str(pasta / "selecao_A"))
    ap.add_argument("--revisora", default="revisora")
    a = ap.parse_args()
    out, sel = Path(a.pasta), Path(a.selecao)
    origem = json.loads((sel / "origem.json").read_text(encoding="utf-8"))
    loc = origem["caminho_local"]
    raiz = (PureWindowsPath if os.name != "nt" and re.match(r"^[A-Za-z]:[\\/]", loc) else Path)(loc)
    nota = {r["caminho_relativo"]: r.get("observacao_ia", "") for r in ler(sel / "revisao_floresta_A_ia.csv")}
    dados = []
    for r in ler(out / "divergencias.csv"):
        dados.append({"n": r["n"], "caminho": r["caminho_relativo"], "split": r["split"], "diverge": r["diverge_em"],
                      "url": (raiz / r["caminho_relativo"]).as_uri(), "nota_ia": nota.get(r["caminho_relativo"], ""),
                      "ia": {c: r[f"{c}_ia"] for c in CAMPOS},
                      "rev": {c: r[f"{c}_{a.revisora}"] for c in CAMPOS}})
    js = lambda o: json.dumps(o, ensure_ascii=False).replace("</", "<\\/")
    html = (HTML.replace("__DATA__", js(dados)).replace("__CAMPOS__", js(CAMPOS)).replace("__CRIT__", js(CRIT))
                .replace("__CHAVE__", js("ignis_desempate_A_" + a.revisora)).replace("__EXPORTAR__", js("desempate_preenchido.csv")))
    (out / "desempate.html").write_text(html, encoding="utf-8")
    print(f"Página gerada: {out / 'desempate.html'} | {len(dados)} imagens para decidir")


if __name__ == "__main__":
    main()
