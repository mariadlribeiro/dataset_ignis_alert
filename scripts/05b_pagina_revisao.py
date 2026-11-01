#!/usr/bin/env python3
"""
Etapa 5b - Gera a PÁGINA DE REVISÃO (HTML local) a partir de revisao.csv + sugestoes.csv.

Abra o arquivo gerado (relatorios/05_sugestoes/revisao.html) no Chrome ou Edge.
  * mostra cada imagem grande, com a sugestão do modelo e atalhos de teclado;
  * linhas de AUDITORIA são cegas: a sugestão e a pasta original só aparecem depois que você
    responde (assim a precisão do modelo é medida sem viés de ancoragem);
  * o progresso fica salvo no navegador; o botão "Exportar CSV" baixa revisao_preenchida.csv;
  * nada no dataset é alterado.

Uso:  python scripts/05b_pagina_revisao.py
"""
import argparse, csv, json
from pathlib import Path

HTML = r"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>Revisão – Ignis Alert</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{--bg:#fff;--fg:#1d1d1f;--mut:#6b6b70;--card:#f4f4f6;--bd:#d6d6dc;--ac:#c2410c;--ok:#15803d;--warn:#b45309;--warnbg:#fef3c7}
@media (prefers-color-scheme:dark){:root{--bg:#161618;--fg:#f0f0f2;--mut:#9a9aa2;--card:#222226;--bd:#3a3a40;--ac:#fb923c;--ok:#4ade80;--warn:#fbbf24;--warnbg:#3a2e0a}}
*{box-sizing:border-box}html,body{height:100%}
body{margin:0;height:100dvh;font:14px/1.35 system-ui,"Segoe UI",sans-serif;background:var(--bg);color:var(--fg);display:flex;flex-direction:column;overflow:hidden}
header{background:var(--card);border-bottom:1px solid var(--bd);padding:6px 12px;display:flex;gap:8px;flex-wrap:wrap;align-items:center}
header b{font-size:15px}.bar{flex:1;min-width:100px;height:8px;background:var(--bd);border-radius:4px;overflow:hidden}
.bar i{display:block;height:100%;background:var(--ok);width:0;transition:width .2s}
button,select,input[type=number],textarea{font:inherit;color:var(--fg);background:var(--bg);border:1px solid var(--bd);border-radius:7px;padding:4px 9px}
button{cursor:pointer;display:inline-flex;align-items:center;gap:5px}button:hover:not(:disabled){border-color:var(--ac)}button:disabled{opacity:.4;cursor:default}
button.pri{background:var(--ac);border-color:var(--ac);color:#fff;font-weight:600}
label.chk{display:flex;gap:5px;align-items:center;cursor:pointer;user-select:none}
.sm{font-size:12px;color:var(--mut)}.pend{color:var(--warn);font-weight:600}
main{flex:1;min-height:0;display:grid;grid-template-columns:minmax(0,1fr) 450px}
@media (max-width:950px){main{grid-template-columns:1fr;grid-template-rows:48% 1fr}}
.esq{display:flex;flex-direction:column;min-height:0;padding:10px 6px 8px 10px;gap:5px}
.foto{position:relative;flex:1;min-height:0;background:#0b0b0c;border-radius:8px;overflow:auto;display:flex;align-items:center;justify-content:center}
.foto img{max-width:100%;max-height:100%;object-fit:contain;cursor:zoom-in}
.foto.zoom{display:block}.foto.zoom img{max-width:none;max-height:none;object-fit:none;cursor:zoom-out}
.badge{position:absolute;top:8px;left:8px;background:#000a;color:#fff;border-radius:12px;padding:2px 10px;font-size:12px;pointer-events:none}
.legenda{display:flex;justify-content:space-between;gap:8px;align-items:center;font-size:12px;color:var(--mut)}
.legenda a{color:var(--ac);text-decoration:none;white-space:nowrap}.legenda span{word-break:break-all}
.mapa{display:flex;flex-wrap:wrap;gap:2px;max-height:46px;overflow:auto}
.mapa i{width:9px;height:9px;border-radius:2px;background:var(--bd);cursor:pointer}
.mapa i.ok{background:var(--ok)}.mapa i.cego{outline:1px solid var(--ac)}.mapa i.cur{background:var(--ac);transform:scale(1.5)}
.atalhos{font-size:11.5px;color:var(--mut)}.atalhos b{color:var(--fg);font-weight:600}
.dir{display:flex;flex-direction:column;min-height:0;padding:10px 12px 8px 6px;gap:6px}
.rolagem{flex:1;min-height:0;overflow-y:auto;display:flex;flex-direction:column;gap:6px;padding-right:2px}
.box{background:var(--card);border:1px solid var(--bd);border-radius:8px;padding:7px 9px}
.box h4{margin:0 0 4px;font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--mut)}
.duas{display:grid;grid-template-columns:1fr 1fr;gap:6px}
.opts{display:flex;flex-wrap:wrap;gap:4px}
.opt{display:inline-flex;align-items:center;gap:4px;padding:4px 8px;border:1px solid var(--bd);border-radius:7px;background:var(--bg);cursor:pointer;user-select:none;font-size:13px}
.opt:hover{border-color:var(--ac)}.opt .ic{font-size:15px;line-height:1}
.opt kbd{font:10px monospace;color:var(--mut);border:1px solid var(--bd);border-radius:3px;padding:0 3px}
.opt.on{background:var(--ac);border-color:var(--ac);color:#fff;font-weight:600}.opt.on kbd{color:#fff;border-color:#fff8}.opt.def{border-style:dashed}
.p{display:inline-block;margin:2px 4px 2px 0;padding:1px 8px;border-radius:10px;background:var(--bg);border:1px solid var(--bd);font-size:13px}
.tag{display:inline-block;background:var(--bg);border:1px solid var(--bd);border-radius:10px;padding:0 8px;font-size:12px;margin:0 4px 3px 0}
.aviso{background:var(--warnbg);color:var(--warn);border-radius:6px;padding:4px 9px;font-size:12.5px;margin-top:3px}
.ok{color:var(--ok);font-weight:600}.no{color:var(--warn);font-weight:600}.cegot{color:var(--ac);font-weight:600}
details summary{cursor:pointer;font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--mut)}details .opts{margin-top:5px}
textarea{width:100%;height:44px;resize:vertical}
.acoes{display:flex;gap:6px;flex-wrap:wrap;padding-top:6px;border-top:1px solid var(--bd)}
.acoes button{flex:1 1 auto;justify-content:center;padding:7px 10px}
#toast{position:fixed;bottom:16px;left:50%;transform:translateX(-50%);background:#000d;color:#fff;padding:7px 16px;border-radius:18px;font-size:13px;opacity:0;transition:opacity .2s;pointer-events:none;z-index:20}
#toast.on{opacity:1}
#modal{display:none;position:fixed;inset:0;background:#000a;z-index:30;align-items:center;justify-content:center;padding:16px}
#modal.on{display:flex}#modal .cx{background:var(--bg);border:1px solid var(--bd);border-radius:12px;max-width:640px;width:100%;max-height:90vh;overflow:auto;padding:16px 18px}
#modal h3{margin:0 0 8px}#modal table{border-collapse:collapse;width:100%;margin:6px 0 10px}#modal td,#modal th{border-bottom:1px solid var(--bd);padding:3px 8px;text-align:left;font-size:13px}
#modal td.n,#modal th.n{text-align:right}
</style></head><body>
<header>
 <b>🔥 Revisão Ignis Alert</b><span id="prog"></span><div class="bar"><i id="barra"></i></div>
 <span id="alt" class="sm"></span>
 <select id="filtro" title="Filtrar imagens por motivo de revisão"></select>
 <label class="chk" title="Passa para a próxima imagem assim que ambiente, fogo e fumaça estiverem marcados"><input type="checkbox" id="auto" checked> ⏩ avançar sozinho</label>
 <span class="sm">ir para #<input id="ir" type="number" min="1" style="width:62px"></span>
 <button id="res" title="Resumo e precisão do modelo na auditoria">📊 Resumo</button>
 <button id="exp" class="pri" title="Baixa o revisao_preenchida.csv">💾 Exportar CSV</button>
 <button id="imp" title="Carrega um revisao_preenchida.csv exportado antes">📂 Importar</button>
 <button id="aj" title="Atalhos de teclado (?)">❓</button>
 <input id="arq" type="file" accept=".csv" hidden>
</header>
<main>
 <section class="esq">
  <div class="foto" id="moldura"><span class="badge" id="badge"></span><img id="foto" alt="imagem em revisão" title="Clique (ou tecla L) para ampliar"></div>
  <div class="legenda"><span id="cap"></span><span><a id="abrir" target="_blank" rel="noopener">↗ abrir em nova aba</a> · <a href="#" id="zoom">🔍 ampliar (L)</a></span></div>
  <div class="mapa" id="mapa" title="Verde = revisada · laranja = atual · contorno = auditoria cega"></div>
  <div class="atalhos"><b>1–7</b> ambiente · <b>Q W E</b> fogo · <b>A S D</b> fumaça · <b>Z X C</b> tipo · <b>← →</b> navegar · <b>Enter</b> aceitar sugestão · <b>N</b> próxima pendente · <b>L</b> ampliar · <b>⌫</b> limpar · <b>?</b> ajuda</div>
 </section>
 <section class="dir">
  <div class="rolagem">
   <div class="box"><h4 id="idx"></h4><div id="motivos"></div><div id="orig"></div><div id="avisos"></div></div>
   <div class="box" id="sug"></div>
   <div id="campos"></div>
   <div class="box"><h4>📝 Observação</h4><textarea id="obs" placeholder="ex.: só fumaça, sem chama; imagem sintética; marca d'água..."></textarea></div>
  </div>
  <div class="acoes">
   <button id="ant" title="← anterior">⬅️ Anterior</button>
   <button id="prox" title="→ próxima">Próxima ➡️</button>
   <button id="nr" title="Tecla N: pula para a próxima imagem ainda não revisada">⏭️ Próx. pendente</button>
   <button id="lim" title="Tecla Backspace: apaga as marcações desta imagem">🧹 Limpar</button>
   <button id="ace" class="pri" title="Tecla Enter: usa a sugestão do modelo nos campos vazios">✅ Aceitar sugestão</button>
  </div>
 </section>
</main>
<div id="toast"></div>
<div id="modal"><div class="cx" id="cx"></div></div>
<script>
const DATA = __DATA__;
const LABEL = {floresta:'Floresta',cidade:'Cidade',casa:'Casa',predios:'Prédios',flores_jardins:'Flores/jardins',outros:'Outros',ambiente_incerto:'Incerto',
  sim:'Sim',nao:'Não',incerto:'Incerto',fotografia:'Foto',sintetica:'Sintética',visualizacao_sensor:'Sensor',
  satelite:'Satélite',drone:'Drone',vigilancia:'Vigilância',celular_terrestre:'Celular'};
const ICON = {floresta:'🌲',cidade:'🏙️',casa:'🏠',predios:'🏢',flores_jardins:'🌸',outros:'🧩',ambiente_incerto:'❔',
  sim:'✅',nao:'🚫',incerto:'❔',fotografia:'📷',sintetica:'🎮',visualizacao_sensor:'📡',
  satelite:'🛰️',drone:'🚁',vigilancia:'📹',celular_terrestre:'📱'};
const ICON_CAMPO = {fogo:{sim:'🔥',nao:'🚫',incerto:'❔'}, fumaca:{sim:'💨',nao:'🚫',incerto:'❔'}};
const icone = (c,v) => (ICON_CAMPO[c.id] && ICON_CAMPO[c.id][v]) || ICON[v] || '';
const CAMPOS = [
 {id:'ambiente',nome:'🌳 Ambiente',op:[['floresta','1'],['cidade','2'],['casa','3'],['predios','4'],['flores_jardins','5'],['outros','6'],['ambiente_incerto','7']]},
 {id:'fogo',nome:'🔥 Fogo visível (chamas)',op:[['sim','q'],['nao','w'],['incerto','e']]},
 {id:'fumaca',nome:'💨 Fumaça',op:[['sim','a'],['nao','s'],['incerto','d']]},
 {id:'tipo',nome:'🖼️ Tipo de imagem',op:[['fotografia','z'],['sintetica','x'],['visualizacao_sensor','c']],padrao:'fotografia'},
 {id:'camera',nome:'🎥 Câmera (opcional)',op:[['satelite','t'],['drone','y'],['vigilancia','u'],['celular_terrestre','i'],['incerto','o']],recolhido:true}
];
const OBRIG = ['ambiente','fogo','fumaca'];
const AVISOS = {
 discorda_da_pasta:'O modelo discorda da pasta original: confira se o rótulo da pasta está certo.',
 pendente_etapa4:'Pendente da Etapa 4 (grupo com conflito de rótulo ou GIF animado).',
 fumaca_sem_fogo:'Possível fumaça sem chama visível.',
 fogo_incerto:'O modelo não decidiu se há fogo.',
 ambiente_incerto:'O modelo não decidiu o ambiente.'
};
const KEY = 'ignis_revisao_v1';
let st = {};
try { st = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch(e) {}
let alteracoes = 0, lista = [], pos = 0;
const $ = id => document.getElementById(id);
const salvar = () => { try { localStorage.setItem(KEY, JSON.stringify(st)); } catch(e) {} };
const reg = r => (st[r.caminho_relativo] = st[r.caminho_relativo] || {});
const val = (r,c) => (reg(r)[c.id] ?? c.padrao ?? '');
const feito = r => OBRIG.every(k => reg(r)[k]);
const cego = r => r.motivos === 'auditoria';
const nRevisadas = () => DATA.filter(feito).length;
function toast(t){ const e=$('toast'); e.textContent=t; e.className='on'; clearTimeout(toast.t); toast.t=setTimeout(()=>{e.className='';},1800); }

function montarFiltro(){
  const mot = [...new Set(DATA.flatMap(r => r.motivos.split(';').filter(Boolean)))].sort();
  const atual = $('filtro').value;
  $('filtro').innerHTML = `<option value="">todas (${DATA.length})</option><option value="__falta">só não revisadas (${DATA.length - nRevisadas()})</option>` +
    mot.map(m => { const t = DATA.filter(r => r.motivos.split(';').includes(m)); const f = t.filter(feito).length;
      return `<option value="${m}">${m} (${f}/${t.length})</option>`; }).join('');
  $('filtro').value = atual;
}
function aplicar(){
  const v = $('filtro').value;
  lista = DATA.filter(r => !v || (v==='__falta' ? !feito(r) : r.motivos.split(';').includes(v)));
  pos = Math.min(pos, Math.max(lista.length-1,0));
  mostrar();
}
function opc(r,c){
  const atual = val(r,c), explicito = reg(r)[c.id];
  return c.op.map(([v,k]) => `<span class="opt ${atual===v?'on':''} ${atual===v&&!explicito?'def':''}" role="button" data-c="${c.id}" data-v="${v}" title="${LABEL[v]} (tecla ${k.toUpperCase()})"><span class="ic">${icone(c,v)}</span>${LABEL[v]}<kbd>${k.toUpperCase()}</kbd></span>`).join('');
}
function bloco(r,c){
  if (c.recolhido) return `<div class="box"><details ${reg(r)[c.id]?'open':''}><summary>${c.nome}</summary><div class="opts">${opc(r,c)}</div></details></div>`;
  return `<div class="box"><h4>${c.nome}</h4><div class="opts">${opc(r,c)}</div></div>`;
}
function concordancia(r){
  const x = reg(r), t = [];
  const par = (nome, mine, sug) => t.push(`${nome}: você <b>${mine}</b> · modelo <b>${sug}</b> ${mine===sug?'<span class="ok">✓ concorda</span>':'<span class="no">✗ discorda</span>'}`);
  par('ambiente', x.ambiente, r.amb_sug); par('fogo', x.fogo, r.fogo_sug); par('fumaça', x.fumaca, r.fum_sug);
  return t.join('<br>');
}
function mostrar(){
  montarFiltro();
  const total = DATA.length, n = nRevisadas();
  $('prog').textContent = `${n}/${total} revisadas`;
  $('barra').style.width = (100*n/total)+'%';
  $('alt').innerHTML = alteracoes ? `<span class="pend">⚠ ${alteracoes} alterações sem exportar</span>` : '';
  const r = lista[pos];
  if (!r){ $('idx').textContent='Nenhuma imagem neste filtro.'; $('campos').innerHTML=''; $('mapa').innerHTML=''; return; }
  const oculto = cego(r) && !feito(r);
  const img = $('foto');
  if (img.dataset.src !== r.url){ img.dataset.src = r.url; img.src = r.url; $('moldura').className = 'foto'; }
  img.onerror = () => { $('cap').textContent = '⚠ Não consegui abrir a imagem: ' + r.url; };
  img.onload = () => { $('cap').textContent = `${r.caminho_relativo} · ${img.naturalWidth}×${img.naturalHeight}px`; };
  $('cap').textContent = r.caminho_relativo;
  $('abrir').href = r.url;
  $('badge').textContent = `#${r.n} · ${pos+1}/${lista.length}`;
  $('idx').innerHTML = `#${r.n} · item ${pos+1} de ${lista.length} ` + (feito(r)?'<span class="ok">✓ revisada</span>':'<span class="no">• pendente</span>');
  $('motivos').innerHTML = r.motivos.split(';').filter(Boolean).map(m=>`<span class="tag">${m}</span>`).join('');
  $('orig').innerHTML = oculto ? '<span class="cegot">🙈 Auditoria cega: pasta e sugestão ficam ocultas até você marcar ambiente, fogo e fumaça.</span>'
     : `<span class="sm">pasta original:</span> <b>${r.classe_original}</b>`;
  $('avisos').innerHTML = r.motivos.split(';').filter(m=>AVISOS[m]).map(m=>`<div class="aviso">⚠ ${AVISOS[m]}</div>`).join('');
  $('sug').innerHTML = oculto ? '<h4>🤖 Sugestão do modelo</h4><span class="sm">oculta</span>' :
     (cego(r) ? `<h4>🎯 Auditoria: você × modelo</h4>${concordancia(r)}` :
     `<h4>🤖 Sugestão do modelo (CLIP)</h4><span class="p">ambiente <b>${LABEL[r.amb_sug]||r.amb_sug}</b> (${r.amb_conf})</span><span class="p">🔥 fogo <b>${LABEL[r.fogo_sug]||r.fogo_sug}</b> (p=${r.fogo_p})</span><span class="p">💨 fumaça <b>${LABEL[r.fum_sug]||r.fum_sug}</b> (p=${r.fum_p})</span><div class="sm">câmera (palpite fraco): ${r.cam_sug}</div>`);
  $('campos').innerHTML = bloco(r,CAMPOS[0]) + `<div class="duas">${bloco(r,CAMPOS[1])}${bloco(r,CAMPOS[2])}</div>` + bloco(r,CAMPOS[3]) + bloco(r,CAMPOS[4]);
  document.querySelectorAll('.opt').forEach(e => e.onclick = () => marcar(e.dataset.c, e.dataset.v));
  $('obs').value = reg(r).obs || '';
  $('obs').oninput = () => { reg(r).obs = $('obs').value; alteracoes++; salvar(); $('alt').innerHTML = `<span class="pend">⚠ ${alteracoes} alterações sem exportar</span>`; };
  $('ace').disabled = oculto;
  $('mapa').innerHTML = lista.map((q,i) => `<i data-i="${i}" class="${feito(q)?'ok':''} ${cego(q)?'cego':''} ${i===pos?'cur':''}" title="#${q.n}"></i>`).join('');
  document.querySelectorAll('.mapa i').forEach(e => e.onclick = () => { pos = +e.dataset.i; mostrar(); });
}
function marcar(c, v){
  const r = lista[pos]; if (!r) return;
  const antes = feito(r), x = reg(r);
  x[c] = (x[c] === v) ? '' : v; alteracoes++; salvar(); mostrar();
  if (!antes && feito(r)){
    const n = nRevisadas();
    if (n % 25 === 0) toast(`💾 ${n} revisadas — exporte o CSV para não perder o trabalho`);
    else toast(cego(r) ? '🎯 auditoria registrada: veja a comparação' : '✓ revisada');
    if ($('auto').checked && !cego(r)) { const alvo = pos; setTimeout(() => { if (pos === alvo) ir(1); }, 300); }
  }
}
function aceitar(){
  const r = lista[pos]; if (!r || (cego(r) && !feito(r))) return;
  const x = reg(r);
  if (!x.ambiente) x.ambiente = r.amb_sug;
  if (!x.fogo) x.fogo = r.fogo_sug;
  if (!x.fumaca) x.fumaca = r.fum_sug;
  alteracoes++; salvar(); toast('✅ sugestão aceita'); ir(1);
}
function limpar(){
  const r = lista[pos]; if (!r) return;
  delete st[r.caminho_relativo]; alteracoes++; salvar(); toast('🧹 marcações desta imagem apagadas'); mostrar();
}
function ir(d){ pos = Math.max(0, Math.min(lista.length-1, pos+d)); mostrar(); }
function proxNaoRevisada(){
  for (let k = 1; k <= lista.length; k++){ const i = (pos + k) % lista.length; if (!feito(lista[i])){ pos = i; mostrar(); return; } }
  toast('🎉 todas as imagens deste filtro estão revisadas');
}
function lupa(){ const m = $('moldura'); m.className = m.className.includes('zoom') ? 'foto' : 'foto zoom'; }

function resumo(){
  const rev = DATA.filter(feito);
  const cont = campo => { const a = {}; rev.forEach(r => { const v = reg(r)[campo]; a[v] = (a[v]||0)+1; }); return a; };
  const tab = (titulo, o) => `<b>${titulo}</b><table>${Object.entries(o).sort((a,b)=>b[1]-a[1]).map(([k,v])=>`<tr><td>${LABEL[k]||k}</td><td class="n">${v}</td></tr>`).join('') || '<tr><td>—</td></tr>'}</table>`;
  const aud = DATA.filter(r => cego(r) && feito(r));
  const pc = f => aud.length ? (100*aud.filter(f).length/aud.length).toFixed(0)+'% ('+aud.filter(f).length+'/'+aud.length+')' : '—';
  const nf = rev.filter(r => /non_fire/i.test(r.classe_original) && reg(r).fogo==='sim').length;
  const fn = rev.filter(r => !/non_fire/i.test(r.classe_original) && reg(r).fogo==='nao').length;
  $('cx').innerHTML = `<h3>📊 Resumo da revisão</h3>
   <p><b>${rev.length}</b> de ${DATA.length} imagens revisadas · auditoria cega concluída: <b>${aud.length}</b> de ${DATA.filter(cego).length}</p>
   ${tab('Ambiente confirmado', cont('ambiente'))}${tab('Fogo confirmado (chamas visíveis)', cont('fogo'))}${tab('Fumaça confirmada', cont('fumaca'))}
   <b>Rótulos da pasta que parecem errados (entre as revisadas)</b><table>
    <tr><td>pasta "sem fogo" com fogo visível</td><td class="n">${nf}</td></tr><tr><td>pasta "com fogo" sem fogo visível</td><td class="n">${fn}</td></tr></table>
   <b>Precisão do modelo na auditoria cega</b><table>
    <tr><td>ambiente</td><td class="n">${pc(r=>reg(r).ambiente===r.amb_sug)}</td></tr>
    <tr><td>fogo</td><td class="n">${pc(r=>reg(r).fogo===r.fogo_sug)}</td></tr>
    <tr><td>fumaça</td><td class="n">${pc(r=>reg(r).fumaca===r.fum_sug)}</td></tr></table>
   <p class="sm">Com poucas imagens auditadas a margem de erro é grande; o número final sai do script 05c.</p>
   <div style="display:flex;gap:8px;justify-content:space-between"><button id="zer">🗑️ Apagar todas as minhas marcações</button><button id="fec" class="pri">Fechar</button></div>`;
  $('modal').className = 'on';
  $('fec').onclick = () => { $('modal').className = ''; };
  $('zer').onclick = () => { if (confirm('Apagar TODAS as marcações salvas neste navegador? Exporte o CSV antes se quiser guardá-las.') && confirm('Tem certeza? Isso não pode ser desfeito.')) { st = {}; salvar(); alteracoes = 0; $('modal').className=''; aplicar(); toast('marcações apagadas'); } };
}
$('modal').onclick = e => { if (e.target.id === 'modal') $('modal').className = ''; };
$('foto').onclick = lupa; $('zoom').onclick = e => { e.preventDefault(); lupa(); };
$('ant').onclick = () => ir(-1); $('prox').onclick = () => ir(1); $('nr').onclick = proxNaoRevisada; $('ace').onclick = aceitar; $('lim').onclick = limpar;
$('res').onclick = resumo;
$('aj').onclick = () => toast('Atalhos: 1–7 ambiente · Q W E fogo · A S D fumaça · Z X C tipo · T Y U I O câmera · ← → · Enter · N · L · Backspace');
$('filtro').onchange = () => { pos = 0; aplicar(); $('filtro').blur(); };
$('ir').onchange = e => { const n = parseInt(e.target.value,10); const i = lista.findIndex(r => r.n===n); if (i>=0){pos=i; mostrar();} else toast('#'+n+' não está neste filtro'); e.target.blur(); };
document.addEventListener('click', e => { const b = e.target.closest && e.target.closest('button'); if (b) b.blur(); });
document.addEventListener('keydown', e => {
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  const t = e.target;
  if (t.tagName === 'TEXTAREA' || (t.tagName === 'INPUT' && t.type === 'number')) return;   // digitando
  if (t.tagName === 'SELECT' || t.tagName === 'BUTTON' || (t.tagName === 'INPUT')) t.blur();   // não deixa o foco travar os atalhos
  if ($('modal').className === 'on'){ if (e.key === 'Escape') $('modal').className = ''; return; }
  const k = e.key.toLowerCase();
  const tratar = f => { e.preventDefault(); f(); };
  if (e.key==='ArrowRight') return tratar(() => ir(1));
  if (e.key==='ArrowLeft') return tratar(() => ir(-1));
  if (e.key==='Enter') return tratar(aceitar);
  if (e.key==='Backspace' || e.key==='Delete') return tratar(limpar);
  if (k==='n') return tratar(proxNaoRevisada);
  if (k==='l') return tratar(lupa);
  if (e.key==='?') return tratar(() => $('aj').onclick());
  for (const c of CAMPOS) for (const [v,tc] of c.op) if (k===tc) return tratar(() => marcar(c.id, v));
});

const esc = s => '"' + String(s ?? '').replace(/"/g,'""') + '"';
function exportar(){
  const cols = ['n','caminho_relativo','classe_original','motivos_revisao','ambiente_sugerido','fogo_sugerido','fumaca_sugerida',
                'ambiente_confirmado','fogo_confirmado','fumaca_confirmada','tipo_imagem','camera_confirmada','observacao','revisado'];
  const linhas = DATA.map(r => { const x = reg(r); return [r.n,r.caminho_relativo,r.classe_original,r.motivos,r.amb_sug,r.fogo_sug,r.fum_sug,
      x.ambiente||'',x.fogo||'',x.fumaca||'',x.tipo||'fotografia',x.camera||'',x.obs||'',feito(r)?'sim':'nao'].map(esc).join(','); });
  const blob = new Blob([cols.join(',')+'\r\n'+linhas.join('\r\n')+'\r\n'], {type:'text/csv;charset=utf-8'});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'revisao_preenchida.csv';
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  alteracoes = 0; mostrar(); toast('💾 CSV exportado: guarde em relatorios/05_sugestoes/');
}
function parseCSV(t){
  const out=[]; let row=[], cur='', q=false;
  for (let i=0;i<t.length;i++){ const ch=t[i];
    if (q){ if (ch==='"'){ if (t[i+1]==='"'){cur+='"';i++;} else q=false; } else cur+=ch; }
    else if (ch==='"') q=true; else if (ch===','){row.push(cur);cur='';}
    else if (ch==='\n'){row.push(cur);out.push(row);row=[];cur='';} else if (ch!=='\r') cur+=ch; }
  if (cur||row.length){row.push(cur);out.push(row);} return out;
}
$('exp').onclick = exportar;
$('imp').onclick = () => $('arq').click();
$('arq').onchange = async e => {
  const f = e.target.files[0]; if (!f) return;
  const t = parseCSV((await f.text()).replace(/^\uFEFF/,'')); const h = t.shift(); const ix = n => h.indexOf(n);
  let c = 0;
  for (const l of t){ const k = l[ix('caminho_relativo')]; if (!k) continue;
    st[k] = {ambiente:l[ix('ambiente_confirmado')],fogo:l[ix('fogo_confirmado')],fumaca:l[ix('fumaca_confirmada')],
             tipo:l[ix('tipo_imagem')],camera:l[ix('camera_confirmada')],obs:l[ix('observacao')]}; c++; }
  salvar(); aplicar(); toast('📂 ' + c + ' linhas importadas');
};
aplicar();
window.addEventListener('beforeunload', e => { if (alteracoes) { e.preventDefault(); e.returnValue = ''; } });
</script></body></html>
"""


def ler(caminho):
    with open(caminho, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--origem", default="relatorios/01_origem/origem.json")
    ap.add_argument("--revisao", default="relatorios/05_sugestoes/revisao.csv")
    ap.add_argument("--sugestoes", default="relatorios/05_sugestoes/sugestoes.csv")
    ap.add_argument("--saida", default="relatorios/05_sugestoes/revisao.html")
    a = ap.parse_args()

    raiz = Path(json.loads(Path(a.origem).read_text(encoding="utf-8"))["caminho_local"])
    sug = {r["caminho_relativo"]: r for r in ler(a.sugestoes)}
    dados = []
    for r in ler(a.revisao):
        s = sug[r["caminho_relativo"]]
        dados.append({
            "n": int(r["n"]), "caminho_relativo": r["caminho_relativo"], "classe_original": r["classe_original"],
            "motivos": r["motivos_revisao"], "url": (raiz / r["caminho_relativo"]).as_uri(),
            "amb_sug": s["ambiente_sugerido"], "amb_conf": s["amb_conf"],
            "fogo_sug": s["fogo_sugerido"], "fogo_p": s["fogo_prob"],
            "fum_sug": s["fumaca_sugerida"], "fum_p": s["fumaca_prob"], "cam_sug": s["camera_sugerida_fraca"]})
    js = json.dumps(dados, ensure_ascii=False).replace("</", "<\\/")
    Path(a.saida).write_text(HTML.replace("__DATA__", js), encoding="utf-8")
    cegas = sum(d["motivos"] == "auditoria" for d in dados)
    print(f"Página gerada: {a.saida}\nImagens: {len(dados)} (das quais {cegas} cegas, de auditoria)")
    print("Abra o arquivo no Chrome ou Edge (duplo clique).")


if __name__ == "__main__":
    main()