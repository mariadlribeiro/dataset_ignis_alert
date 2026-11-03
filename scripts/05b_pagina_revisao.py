#!/usr/bin/env python3
"""
Etapa 5b - Gera a PÁGINA DE REVISÃO (HTML local) a partir de revisao.csv + sugestoes.csv.

Abra o arquivo gerado (relatorios/05_sugestoes/revisao.html) no Chrome ou Edge.
  * mostra cada imagem grande, com a ficha técnica (Etapa 2), o grupo de duplicatas (Etapa 3),
    o split (Etapa 4) e as probabilidades do modelo comparadas aos limiares (Etapa 5a);
  * critérios de cada rótulo ficam visíveis ao lado das opções, para manter a revisão consistente;
  * linhas de AUDITORIA são cegas: pasta, caminho, sugestão e grupo só aparecem depois que você
    responde. A PRIMEIRA resposta da auditoria fica gravada em *_cego e não muda se você corrigir
    depois de ver o modelo;
  * o progresso fica salvo no navegador; o botão "Exportar CSV" baixa revisao_preenchida.csv;
  * nada no dataset é alterado.

Modo "ambiente" (2ª revisão, lista do 05c): só o ambiente é obrigatório; fogo e fumaça ficam opcionais
(marque só se o modelo errou) e o CSV exportado se chama revisao_ambiente_preenchida.csv.

Uso:  python scripts/05b_pagina_revisao.py                  # 1ª revisão (revisao.csv)
      python scripts/05b_pagina_revisao.py --modo ambiente  # 2ª revisão (revisao_ambiente.csv)
"""
import argparse, csv, json
from collections import defaultdict
from pathlib import Path

LIM_PADRAO = {"amb_conf_min": 0.45, "amb_margem_min": 0.15, "p_sim": 0.80, "p_nao": 0.20, "fumaca_revisar": 0.50}

HTML = r"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>Revisão – Ignis Alert</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{
  --papel:#f3f4f1; --folha:#ffffff; --tinta:#1e2421; --mudo:#5f6862; --linha:#d5d9d3; --linha2:#e6e9e4;
  --brasa:#b93d0f; --brasa-suave:#fbe7dc; --mata:#2d6a4a; --mata-suave:#dff0e6; --fumo:#5b6b7a; --fumo-suave:#e5eaef;
  --ambar:#9a5b00; --ambar-suave:#fdf0d5; --foco:#1f5fbf; --palco:#1a1d1b;
}
@media (prefers-color-scheme:dark){:root{
  --papel:#151816; --folha:#1d211f; --tinta:#e9ece8; --mudo:#9aa39d; --linha:#343a36; --linha2:#2a2f2c;
  --brasa:#f0844f; --brasa-suave:#3a2216; --mata:#6cc596; --mata-suave:#1b3327; --fumo:#a3b3c2; --fumo-suave:#232b33;
  --ambar:#f2b44d; --ambar-suave:#3a2c10; --foco:#7fb0ff; --palco:#0e100f;
}}
*{box-sizing:border-box} html,body{height:100%}
body{margin:0;height:100dvh;display:flex;flex-direction:column;overflow:hidden;background:var(--papel);color:var(--tinta);
  font:14px/1.45 "Segoe UI Variable Text","Segoe UI",system-ui,sans-serif;font-variant-numeric:tabular-nums}
:focus-visible{outline:2px solid var(--foco);outline-offset:2px}
button,select,input,textarea{font:inherit;color:inherit}
button{cursor:pointer;background:var(--folha);border:1px solid var(--linha);border-radius:6px;padding:5px 11px;display:inline-flex;align-items:center;gap:6px}
button:hover:not(:disabled){border-color:var(--tinta)} button:disabled{opacity:.4;cursor:default}
button.forte{background:var(--brasa);border-color:var(--brasa);color:#fff;font-weight:600}
select,input[type=number]{background:var(--folha);border:1px solid var(--linha);border-radius:6px;padding:4px 8px}
kbd{font:600 10.5px/1 "Cascadia Mono",Consolas,monospace;border:1px solid var(--linha);border-bottom-width:2px;border-radius:4px;padding:2px 4px;color:var(--mudo);background:var(--folha)}

/* ---------- topo ---------- */
header{display:flex;align-items:center;gap:14px;padding:8px 16px;background:var(--folha);border-bottom:1px solid var(--linha);flex-wrap:wrap}
.marca{font-weight:700;font-size:15px;letter-spacing:-.01em;white-space:nowrap}
.marca small{font-weight:400;color:var(--mudo);margin-left:6px}
.progresso{display:flex;flex-direction:column;gap:3px;min-width:170px;flex:1;max-width:400px}
@media (max-width:1400px){.marca small{display:none}}
@media (max-width:1300px){.ferr .curto{display:none}}
.progresso .rot{display:flex;justify-content:space-between;font-size:12.5px;color:var(--mudo)}
.progresso .rot b{color:var(--tinta)}
.trilha{height:7px;border-radius:4px;background:var(--linha2);overflow:hidden;display:flex}
.trilha i{display:block;height:100%}
.ferr{display:flex;gap:8px;align-items:center;margin-left:auto;flex-wrap:wrap}
.pend{background:#fff;color:var(--brasa);border-radius:9px;padding:0 6px;font-size:11.5px;font-weight:700;margin-left:2px}

/* ---------- área principal ---------- */
main{flex:1;min-height:0;display:grid;grid-template-columns:minmax(0,1fr) 470px}
@media (max-width:1000px){main{grid-template-columns:1fr;grid-template-rows:52% 1fr}}
.esq{display:flex;flex-direction:column;min-height:0;padding:12px 8px 10px 14px;gap:8px}
.palco{position:relative;flex:1;min-height:0;background:var(--palco);border-radius:8px;overflow:auto;display:flex;align-items:center;justify-content:center}
.palco img{max-width:100%;max-height:100%;object-fit:contain;cursor:zoom-in}
.palco.zoom{display:block}.palco.zoom img{max-width:none;max-height:none;cursor:zoom-out}
.selo{position:absolute;top:10px;left:10px;background:#000b;color:#fff;border-radius:5px;padding:3px 9px;font-size:12.5px;pointer-events:none}
.selo.cego{background:var(--brasa)}
.ficha{display:flex;flex-wrap:wrap;gap:4px 18px;font-size:12.5px;color:var(--mudo);align-items:baseline}
.ficha b{color:var(--tinta);font-weight:600}
.ficha .cam{flex-basis:100%;word-break:break-all;color:var(--tinta);display:flex;gap:12px}
.ficha a{color:var(--foco);text-decoration:none;margin-left:auto;white-space:nowrap}
.alerta-f{color:var(--ambar)}
.grupo{background:var(--folha);border:1px solid var(--linha);border-radius:8px;padding:8px 10px}
.grupo h3{margin:0 0 6px;font-size:13px;font-weight:600}
.grupo h3 span{font-weight:400;color:var(--mudo)}
.miniaturas{display:flex;gap:8px;overflow-x:auto;padding-bottom:2px}
.mini{flex:0 0 auto;width:124px;font-size:11px;color:var(--mudo);cursor:pointer;border-radius:5px}
.mini img{width:124px;height:72px;object-fit:cover;border-radius:5px;display:block;border:2px solid transparent;background:var(--palco)}
.mini.atual img{border-color:var(--brasa)}
.mini span{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px}
.mapa{display:flex;flex-wrap:wrap;gap:2px;max-height:50px;overflow:auto}
.mapa i{width:10px;height:10px;border-radius:2px;background:var(--linha);cursor:pointer}
.mapa i.ok{background:var(--mata)} .mapa i.aud{box-shadow:inset 0 0 0 2px var(--brasa)}
.mapa i.cur{outline:2px solid var(--tinta);outline-offset:1px}
.legenda-mapa{display:flex;gap:14px;font-size:11.5px;color:var(--mudo);align-items:center;flex-wrap:wrap}
.legenda-mapa i{display:inline-block;width:10px;height:10px;border-radius:2px;vertical-align:-1px;margin-right:4px}

/* ---------- painel direito ---------- */
.dir{display:flex;flex-direction:column;min-height:0;background:var(--folha);border-left:1px solid var(--linha)}
.rolagem{flex:1;min-height:0;overflow-y:auto;padding:12px 16px 4px}
.sec{padding:10px 0 12px;border-bottom:1px solid var(--linha2)}
.duas .sec{border-bottom:0}
.duas{border-bottom:1px solid var(--linha2)}
.sec h2{margin:0 0 6px;font-size:14px;font-weight:650;display:flex;align-items:baseline;gap:8px}
.sec h2 .n{display:inline-grid;place-items:center;width:20px;height:20px;border-radius:50%;background:var(--linha);color:var(--tinta);font-size:11.5px;font-weight:700;flex:none;transform:translateY(-1px)}
.sec h2 .n.ok{background:var(--mata);color:#fff}
.sec h2 .dica{font-weight:400;font-size:12px;color:var(--mudo);margin-left:auto}
.crit{font-size:12.5px;color:var(--mudo);margin:0 0 7px}
.status .est{font-weight:650}
.est.ok{color:var(--mata)} .est.no{color:var(--ambar)}
.motivo{display:block;margin-top:6px;padding:6px 9px;border-radius:6px;background:var(--ambar-suave);color:var(--tinta);font-size:12.5px}
.motivo b{color:var(--ambar)}
.motivo.aud{background:var(--brasa-suave)} .motivo.aud b{color:var(--brasa)}
.orig{font-size:12.5px;color:var(--mudo);margin-top:6px}.orig b{color:var(--tinta)}

/* modelo */
.medida{display:grid;grid-template-columns:62px 1fr 168px;gap:4px 10px;align-items:center;font-size:12.5px;margin:7px 0 2px}
.medida .nome{color:var(--mudo)} .medida .val{text-align:right;white-space:nowrap} .medida .val b{font-weight:650}
.escala{position:relative;height:14px;border-radius:4px;display:flex}
.escala span{display:block;height:100%}
.escala .z-nao{border-radius:4px 0 0 4px} .escala .z-sim{border-radius:0 4px 4px 0}
.z-nao{background:var(--mata-suave)} .z-inc{background:var(--linha2)} .z-sim{background:var(--brasa-suave)}
.escala .pino{position:absolute;top:-3px;bottom:-3px;width:4px;margin-left:-2px;background:var(--tinta);border-radius:2px}
.escala .corte{position:absolute;top:0;bottom:0;width:0;border-left:1px dashed var(--mudo)}
.barra{position:relative;height:10px;border-radius:5px;background:var(--linha2)}
.barra i{position:absolute;left:0;top:0;bottom:0;border-radius:5px;background:var(--fumo)}
.barra .corte{position:absolute;top:-3px;bottom:-3px;border-left:2px solid var(--tinta)}
.nota{font-size:11.5px;color:var(--mudo);margin-top:3px}
.nota b{color:var(--tinta)}
.oculto{font-size:12.5px;color:var(--mudo);padding:8px 10px;border:1px dashed var(--linha);border-radius:6px}
.comp{font-size:12.5px;display:grid;grid-template-columns:62px 1fr 1fr 18px;gap:3px 10px;align-items:baseline;margin-bottom:6px}
.comp .cab{color:var(--mudo);font-size:11.5px}
.ok{color:var(--mata);font-weight:700} .no{color:var(--ambar);font-weight:700}

/* opções */
.opcoes{display:flex;flex-wrap:wrap;gap:5px}
.opt{display:inline-flex;align-items:center;gap:6px;padding:5px 9px;border:1px solid var(--linha);border-radius:6px;background:var(--folha);cursor:pointer;user-select:none;font-size:13px}
.opt:hover{border-color:var(--tinta)} .opt .ic{font-size:15px;line-height:1}
.opt.on{background:var(--tinta);border-color:var(--tinta);color:var(--folha);font-weight:600}
.opt.on kbd{background:transparent;color:var(--folha);border-color:#fff6}
.opt.sug:not(.on){border:1px dashed var(--fumo);background:var(--fumo-suave)}
.opt.padrao{opacity:.85}
.def{font-size:12px;color:var(--mudo);margin-top:6px}.def:empty{display:none}
.def b{color:var(--tinta)}
.duas{display:grid;grid-template-columns:1fr 1fr;gap:14px}
details.criterios{font-size:12.5px;color:var(--mudo);margin-top:4px}
details.criterios summary{cursor:pointer;color:var(--foco);width:max-content}
details.criterios dl{display:grid;grid-template-columns:auto 1fr;gap:3px 10px;margin:6px 0 0}
details.criterios dt{color:var(--tinta);font-weight:600}
details.criterios dd{margin:0}
textarea{width:100%;height:52px;resize:vertical;background:var(--folha);border:1px solid var(--linha);border-radius:6px;padding:6px 8px}
.chips{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:6px}
.chip{font-size:12px;border:1px solid var(--linha);border-radius:12px;padding:1px 9px;cursor:pointer;background:var(--folha)}
.chip:hover{border-color:var(--tinta)}
.acoes{display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;padding:10px 16px 12px;border-top:1px solid var(--linha);background:var(--folha)}
.acoes button{justify-content:center;padding:7px 8px}
.acoes .larga{grid-column:span 2}

#toast{position:fixed;bottom:18px;left:50%;transform:translateX(-50%);background:var(--tinta);color:var(--folha);padding:8px 16px;border-radius:6px;font-size:13px;opacity:0;transition:opacity .2s;pointer-events:none;z-index:20}
#toast.on{opacity:1}
#modal{display:none;position:fixed;inset:0;background:#0009;z-index:30;align-items:center;justify-content:center;padding:16px}
#modal.on{display:flex}
#modal .cx{background:var(--folha);border:1px solid var(--linha);border-radius:10px;max-width:720px;width:100%;max-height:90vh;overflow:auto;padding:18px 22px}
#modal h3{margin:0 0 10px;font-size:17px} #modal h4{margin:16px 0 4px;font-size:13.5px}
#modal table{border-collapse:collapse;width:100%;margin:4px 0}
#modal td,#modal th{border-bottom:1px solid var(--linha2);padding:4px 8px;text-align:left;font-size:13px}
#modal th{color:var(--mudo);font-weight:600} #modal .n{text-align:right}
.colunas{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style></head><body>
<header>
 <div class="marca">Revisão do dataset<small id="dsnome"></small></div>
 <div class="progresso">
  <div class="rot"><span><b id="nrev">0</b> de <span id="ntot"></span> revisadas</span><span id="caud">auditoria cega <b id="naud">0</b> de <span id="ntaud"></span></span></div>
  <div class="trilha"><i id="t1" style="background:var(--mata)"></i></div>
 </div>
 <div class="ferr">
  <select id="filtro" title="Mostrar só um motivo de revisão"></select>
  <label title="Pula para a próxima imagem assim que ambiente, fogo e fumaça estiverem marcados" style="display:flex;gap:5px;align-items:center;font-size:13px"><input type="checkbox" id="auto" checked> Avançar<span class="curto"> sozinho</span></label>
  <label style="font-size:13px"><span class="curto">Ir para </span>nº <input id="ir" type="number" min="1" style="width:64px"></label>
  <button id="res">Resumo</button>
  <button id="imp" title="Carrega um revisao_preenchida.csv exportado antes">Importar</button>
  <button id="exp" class="forte" title="Baixa o CSV preenchido">Exportar CSV<span id="alt"></span></button>
  <button id="aj" title="Atalhos de teclado (?)" aria-label="Atalhos de teclado">?</button>
  <input id="arq" type="file" accept=".csv" hidden>
 </div>
</header>
<main>
 <section class="esq">
  <div class="palco" id="palco"><span class="selo" id="selo"></span><img id="foto" alt="imagem em revisão" title="Clique ou tecla L para ver em tamanho real"></div>
  <div class="ficha" id="ficha"></div>
  <div class="grupo" id="grupo" hidden></div>
  <div class="mapa" id="mapa"></div>
  <div class="legenda-mapa"><span><i style="background:var(--linha)"></i>pendente</span><span><i style="background:var(--mata)"></i>revisada</span><span><i style="box-shadow:inset 0 0 0 2px var(--brasa)"></i>auditoria cega</span><span>clique num quadrado para ir até a imagem</span></div>
 </section>
 <section class="dir">
  <div class="rolagem">
   <div class="sec" id="s-situacao"></div>
   <div class="sec" id="s-modelo"></div>
   <div id="campos"></div>
   <div class="sec">
    <h2>Observação <span class="dica">vai para o CSV</span></h2>
    <div class="chips" id="chips"></div>
    <textarea id="obs" placeholder="Algo que explique a decisão: só fumaça sem chama, marca d'água, imagem sintética…"></textarea>
   </div>
  </div>
  <div class="acoes">
   <button id="ant" title="Seta para a esquerda">← Anterior</button>
   <button id="prox" title="Seta para a direita">Próxima →</button>
   <button id="nr" title="Tecla N">Próxima pendente</button>
   <button id="lim" title="Backspace: apaga as marcações desta imagem">Limpar marcações</button>
   <button id="ace" class="forte larga" title="Enter: preenche os campos vazios com a sugestão do modelo">Aceitar sugestão nos campos vazios</button>
  </div>
 </section>
</main>
<div id="toast" role="status"></div>
<div id="modal"><div class="cx" id="cx" role="dialog" aria-modal="true"></div></div>
<script>
const DATA = __DATA__;
const GRUPOS = __GRUPOS__;
const LIM = __LIM__;
const DATASET = __DATASET__;
const MODO = __MODO__;
const EXPORTAR_COMO = __EXPORTAR_COMO__;

const LABEL = {floresta:'Floresta',cidade:'Cidade',casa:'Casa',predios:'Prédios',flores_jardins:'Flores e jardins',outros:'Outros',ambiente_incerto:'Incerto',
  sim:'Sim',nao:'Não',incerto:'Incerto',fotografia:'Fotografia',sintetica:'Sintética',visualizacao_sensor:'Sensor',
  satelite:'Satélite',drone:'Drone',vigilancia:'Vigilância',celular_terrestre:'Do chão',
  treino:'treino',validacao:'validação',teste:'teste'};
const ICON = {floresta:'🌲',cidade:'🏙️',casa:'🏠',predios:'🏢',flores_jardins:'🌸',outros:'🧩',ambiente_incerto:'❔',
  fotografia:'📷',sintetica:'🎮',visualizacao_sensor:'📡',satelite:'🛰️',drone:'🚁',vigilancia:'📹',celular_terrestre:'📱'};
const ICON_CAMPO = {fogo:{sim:'🔥',nao:'🚫',incerto:'❔'}, fumaca:{sim:'💨',nao:'🚫',incerto:'❔'}, camera:{incerto:'❔'}};
const icone = (campo, v) => (ICON_CAMPO[campo] && ICON_CAMPO[campo][v]) || ICON[v] || '';
const DEF = {
 ambiente:{floresta:'Mata, bosque, vegetação densa ou paisagem florestal vista de longe.',
   cidade:'Rua, bairro ou espaço público urbano.', casa:'Residência por fora ou por dentro, quintal.',
   predios:'Prédio comercial, industrial, fábrica ou arranha-céu.', flores_jardins:'Flores, jardim ou plantas ornamentais em primeiro plano.',
   outros:'Campo aberto, montanha, lago, veículo, objeto ou pessoa em destaque.', ambiente_incerto:'Não dá para dizer onde é (close no fogo, imagem escura, recorte).'},
 fogo:{sim:'Há chama visível, mesmo pequena.', nao:'Nenhuma chama. Brilho, céu laranja, brasa sem chama ou só fumaça contam como Não.', incerto:'Não dá para afirmar se há chama.'},
 fumaca:{sim:'Fumaça ou névoa de queima visível.', nao:'Ar limpo. Neblina comum ou nuvem não contam.', incerto:'Pode ser fumaça, neblina ou nuvem: não dá para afirmar.'},
 tipo:{fotografia:'Foto real de câmera.', sintetica:'Jogo, CGI, ilustração, montagem.', visualizacao_sensor:'LiDAR, mapa de calor ou outra visualização de sensor.'},
 camera:{satelite:'Vista de cima, a partir do espaço.', drone:'Vista aérea baixa, de drone ou aeronave.', vigilancia:'Câmera fixa, geralmente alta, com ângulo largo.',
   celular_terrestre:'Pessoa no chão, com celular ou câmera de mão.', incerto:'Não dá para dizer.'}
};
const CAMPOS = [
 {id:'ambiente',nome:'Ambiente',crit:'Onde a cena acontece, não o que está queimando.',sug:'amb_sug',
  op:[['floresta','1'],['cidade','2'],['casa','3'],['predios','4'],['flores_jardins','5'],['outros','6'],['ambiente_incerto','7']]},
 {id:'fogo',nome:'Fogo',crit:'Sim só com chama visível.',sug:'fogo_sug',op:[['sim','q'],['nao','w'],['incerto','e']]},
 {id:'fumaca',nome:'Fumaça',crit:'Independe do fogo.',sug:'fum_sug',op:[['sim','a'],['nao','s'],['incerto','d']]},
 {id:'tipo',nome:'Tipo de imagem',crit:'Fotografia já vem marcada; troque só se não for foto real.',op:[['fotografia','z'],['sintetica','x'],['visualizacao_sensor','c']],padrao:'fotografia'},
 {id:'camera',nome:'Câmera',crit:'De onde a imagem foi feita.',sug:'cam_sug',op:[['satelite','t'],['drone','y'],['vigilancia','u'],['celular_terrestre','i'],['incerto','o']],opcional:true}
];
const OBRIG = MODO === 'ambiente' ? ['ambiente'] : ['ambiente','fogo','fumaca'];
if (MODO === 'ambiente') CAMPOS.forEach(c => { if (c.id==='fogo' || c.id==='fumaca'){ c.opcional = true; c.crit = 'Só marque se a sugestão do modelo estiver errada.'; } });
const MOTIVO = {
 auditoria:['Auditoria cega','Amostra aleatória das imagens em que o modelo estava seguro. Serve para medir quanto ele acerta: responda sem ver a sugestão.'],
 discorda_da_pasta:['Discorda da pasta','O modelo acha que o rótulo da pasta original está errado. Confira com atenção.'],
 pendente_etapa4:['Pendente da divisão','Ficou fora de treino/validação/teste na Etapa 4.'],
 fumaca_sem_fogo:['Fumaça sem fogo','O modelo vê fumaça mas não tem certeza de chama. Decida se há chama visível.'],
 fogo_incerto:['Fogo incerto','A probabilidade de fogo ficou entre os limites de Não e Sim.'],
 ambiente_incerto:['Ambiente incerto','O modelo não teve confiança ou margem suficiente para escolher o ambiente.'],
 ambiente_nao_confiavel:['Ambiente não confiável','O modelo estava seguro, mas a auditoria cega mostrou que ele erra muito quando sugere este ambiente. Marque só o ambiente.']
};
const OBS_RAPIDAS = ['só fumaça, sem chama','brilho ou céu laranja sem chama','marca d\'água','texto ou logotipo sobreposto','imagem sintética','montagem ou colagem','imagem muito escura','quase duplicata de outra'];

const KEY = 'ignis_revisao_v2';
let st = {};
try { st = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch(e) {}
let alteracoes = 0, lista = [], pos = 0;
const POR_CAMINHO = Object.fromEntries(DATA.map(r => [r.caminho_relativo, r]));
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const salvar = () => { try { localStorage.setItem(KEY, JSON.stringify(st)); } catch(e) {} };
const reg = r => (st[r.caminho_relativo] = st[r.caminho_relativo] || {});
const val = (r,c) => (reg(r)[c.id] || c.padrao || '');
const feito = r => OBRIG.every(k => reg(r)[k]);
const cego = r => r.motivos === 'auditoria';
const oculta = r => cego(r) && !feito(r) && !reg(r).cego;
const nRevisadas = () => DATA.filter(feito).length;
const motivos = r => r.motivos.split(';').filter(Boolean);
const lbl = v => LABEL[v] || v || '—';
function toast(t){ const e=$('toast'); e.textContent=t; e.className='on'; clearTimeout(toast.t); toast.t=setTimeout(()=>{e.className='';},2000); }

function montarFiltro(){
  const mot = [...new Set(DATA.flatMap(motivos))].sort((a,b) => (b==='auditoria')-(a==='auditoria') || a.localeCompare(b));
  const atual = $('filtro').value;
  $('filtro').innerHTML = `<option value="">Todas as imagens (${nRevisadas()}/${DATA.length})</option><option value="__falta">Só as não revisadas (${DATA.length - nRevisadas()})</option>` +
    mot.map(m => { const t = DATA.filter(r => motivos(r).includes(m)); const f = t.filter(feito).length;
      return `<option value="${m}">${(MOTIVO[m]||[m])[0]} (${f}/${t.length})</option>`; }).join('');
  $('filtro').value = atual;
}
function aplicar(){
  const v = $('filtro').value;
  lista = DATA.filter(r => !v || (v==='__falta' ? !feito(r) : motivos(r).includes(v)));
  pos = Math.min(pos, Math.max(lista.length-1,0));
  mostrar();
}

/* ---------- blocos do painel ---------- */
function secSituacao(r){
  const x = reg(r), oc = oculta(r);
  const falta = OBRIG.filter(k=>!x[k]).map(k=>CAMPOS.find(c=>c.id===k).nome.toLowerCase());
  let h = `<h2>Imagem nº ${r.n} <span class="dica">${pos+1} de ${lista.length} neste filtro</span></h2>`;
  h += `<div class="status">${feito(r) ? '<span class="est ok">✓ Revisada</span>' : '<span class="est no">Falta marcar ' + falta.join(', ').replace(/, ([^,]*)$/, ' e $1') + '</span>'}</div>`;
  h += motivos(r).map(m => { const [t,d] = MOTIVO[m] || [m,'']; return `<span class="motivo ${m==='auditoria'?'aud':''}"><b>${t}.</b> ${d}${m==='pendente_etapa4' && r.pendente ? ' Motivo: ' + esc(r.pendente) + '.' : ''}</span>`; }).join('');
  h += oc ? `<div class="orig">Pasta original, caminho e grupo de duplicatas ficam ocultos até você marcar ambiente, fogo e fumaça.</div>`
          : `<div class="orig">Pasta original: <b>${esc(r.classe_original)}</b></div>`;
  return h;
}
const pc = v => (100*Math.min(Math.max(v,0),1)).toFixed(1)+'%';
function escalaProb(p, cortes){
  return `<div class="escala" role="img" aria-label="probabilidade ${p}"><span class="z-nao" style="width:${pc(LIM.p_nao)}"></span><span class="z-inc" style="width:${pc(LIM.p_sim-LIM.p_nao)}"></span><span class="z-sim" style="flex:1"></span>` +
    (cortes||[]).map(c => `<span class="corte" style="left:${pc(c)}"></span>`).join('') + `<span class="pino" style="left:${pc(p)}"></span></div>`;
}
function barra(v, corte){ return `<div class="barra"><i style="width:${pc(v)}"></i>${corte!=null?`<span class="corte" style="left:${pc(corte)}"></span>`:''}</div>`; }
function secModelo(r){
  if (oculta(r)) return `<h2>Sugestão do modelo</h2><div class="oculto">Oculta na auditoria cega. Aparece depois que você marcar ambiente, fogo e fumaça.</div>`;
  const x = reg(r);
  if (cego(r)){
    const c = x.cego || {};
    const lin = (nome,k,sug) => { const m = c[k], ag = x[k], okk = m === sug;
      return `<span class="nota" style="margin:0">${nome}</span><span>${icone(k,m)} ${lbl(m)}${ag && ag!==m ? ` <span class="nota">(depois: ${lbl(ag)})</span>`:''}</span><span>${icone(k,sug)} ${lbl(sug)}</span><span class="${okk?'ok':'no'}">${okk?'✓':'✗'}</span>`; };
    return `<h2>Auditoria: você × modelo</h2><div class="comp"><span></span><span class="cab">Sua 1ª resposta</span><span class="cab">Modelo</span><span></span>` +
      lin('Ambiente','ambiente',r.amb_sug) + lin('Fogo','fogo',r.fogo_sug) + lin('Fumaça','fumaca',r.fum_sug) +
      `</div><div class="nota">O acerto do modelo usa só a 1ª resposta. Se você corrigir, a correção vale para o rótulo final.</div>` + detalhesModelo(r);
  }
  return `<h2>Sugestão do modelo <span class="dica">CLIP, sem olhar a pasta</span></h2>` + detalhesModelo(r);
}
function detalhesModelo(r){
  const f = +r.fogo_p, u = +r.fum_p, ac = +r.amb_conf, mg = +r.amb_margem;
  const ambOk = ac >= LIM.amb_conf_min && mg >= LIM.amb_margem_min;
  return `
   <div class="medida"><span class="nome">Ambiente</span>${barra(ac, LIM.amb_conf_min)}<span class="val">${icone('ambiente',r.amb_top1)} <b>${lbl(r.amb_top1)}</b> ${ac.toFixed(2)}</span></div>
   <div class="nota">2ª opção: ${lbl(r.amb_top2)}, margem ${mg.toFixed(2)}. Exige confiança ≥ ${LIM.amb_conf_min} (traço) e margem ≥ ${LIM.amb_margem_min}: ${ambOk ? 'atingiu.' : 'não atingiu, por isso sugere <b>Incerto</b>.'}</div>
   <div class="medida"><span class="nome">Fogo</span>${escalaProb(f)}<span class="val"><b>${lbl(r.fogo_sug)}</b> p = ${f.toFixed(2)}</span></div>
   <div class="medida"><span class="nome">Fumaça</span>${escalaProb(u,[LIM.fumaca_revisar])}<span class="val"><b>${lbl(r.fum_sug)}</b> p = ${u.toFixed(2)}</span></div>
   <div class="nota" title="O tracejado da fumaça (${LIM.fumaca_revisar}) manda a imagem para revisão quando não há fogo certo. O modelo confunde brilho do fogo com fumaça.">Verde: Não (p ≤ ${LIM.p_nao}). Cinza: Incerto. Laranja: Sim (p ≥ ${LIM.p_sim}). A fumaça do modelo é pouco confiável.</div>
   <div class="medida"><span class="nome">Câmera</span>${barra(+r.cam_conf)}<span class="val">${lbl(r.cam_sug)} ${(+r.cam_conf).toFixed(2)} <span class="nota">(palpite fraco)</span></span></div>`;
}
function opcoes(r,c){
  const atual = val(r,c), explicito = reg(r)[c.id], sug = (!oculta(r) && c.sug) ? r[c.sug] : null;
  return c.op.map(([v,k]) => {
    const cls = ['opt', atual===v?'on':'', atual===v&&!explicito?'padrao':'', sug===v?'sug':''].join(' ');
    return `<span class="${cls}" role="button" tabindex="0" data-c="${c.id}" data-v="${v}" title="${esc((DEF[c.id]||{})[v]||'')}${sug===v?' (sugestão do modelo)':''}"><span class="ic">${icone(c.id,v)}</span>${lbl(v)} <kbd>${k.toUpperCase()}</kbd></span>`;
  }).join('');
}
function secCampo(r,c,i){
  const x = reg(r), v = val(r,c);
  const sug = c.sug && !oculta(r) ? r[c.sug] : '';
  const def = v ? `<b>${lbl(v)}:</b> ${esc((DEF[c.id]||{})[v]||'')}` : (sug && c.id==='ambiente' ? 'O contorno tracejado marca a sugestão do modelo.' : '');
  const dl = `<details class="criterios"><summary>Ver critérios de todas as opções</summary><dl>${c.op.map(([o])=>`<dt>${lbl(o)}</dt><dd>${esc(DEF[c.id][o])}</dd>`).join('')}</dl></details>`;
  return `<div class="sec"><h2><span class="n ${x[c.id]?'ok':''}">${i}</span>${c.nome}${c.opcional?' <span class="dica">opcional</span>':''}</h2>
    <p class="crit">${c.crit}</p><div class="opcoes">${opcoes(r,c)}</div><div class="def">${def}</div>${['ambiente','fogo','fumaca'].includes(c.id)?dl:''}</div>`;
}
function fichaTecnica(r){
  const oc = oculta(r);
  const fl = (r.flags||'').split(';').filter(Boolean).filter(f => f !== 'extensao_difere_do_formato');
  const ext = (r.flags||'').includes('extensao_difere_do_formato');
  return [
    `<span>Tamanho <b>${r.largura && r.altura ? r.largura+' × '+r.altura+' px' : '—'}</b></span>`,
    `<span>Formato real <b>${esc(r.formato||'—')}</b>${ext?' <span class="alerta-f">(extensão não confere)</span>':''}</span>`,
    `<span>Cor <b>${esc(r.modo||'—')}</b></span>`,
    `<span>Divisão <b>${r.split ? lbl(r.split) : 'fora da divisão'}</b></span>`,
    oc ? '' : `<span>Grupo <b>${esc(r.grupo)}</b>${GRUPOS[r.grupo] ? ', '+GRUPOS[r.grupo].length+' imagens' : ', imagem única'}</span>`,
    fl.length ? `<span class="alerta-f">Alertas: ${fl.map(esc).join(', ')}</span>` : '',
    oc ? `<span class="cam" style="color:var(--mudo)">Caminho oculto na auditoria cega</span>` : `<span class="cam"><span>${esc(r.caminho_relativo)}</span><a href="${r.url}" target="_blank" rel="noopener">Abrir em nova aba</a></span>`
  ].join('');
}
function grupoDuplicatas(r){
  const g = GRUPOS[r.grupo];
  if (!g || oculta(r)) return '';
  return `<h3>Mesmo grupo de duplicatas <span>${g.length} imagens que ficam sempre no mesmo split. Os rótulos devem ser coerentes entre elas.</span></h3><div class="miniaturas">` +
    g.map(m => { const q = POR_CAMINHO[m.c]; const x = st[m.c] || {};
      const est = !q ? 'não está na revisão' : (OBRIG.every(k=>x[k]) ? `nº ${q.n}: ${lbl(x.ambiente)}, fogo ${lbl(x.fogo).toLowerCase()}` : `nº ${q.n}: pendente`);
      return `<div class="mini ${m.c===r.caminho_relativo?'atual':''}" data-c="${esc(m.c)}" title="${esc(m.c)}"><img src="${m.u}" alt="" loading="lazy"><span>${esc(m.c.split('/').pop())}</span><span>${est}</span></div>`; }).join('') + '</div>';
}

function mostrar(){
  montarFiltro();
  const total = DATA.length, n = nRevisadas(), aud = DATA.filter(cego), audF = aud.filter(r => reg(r).cego).length;
  $('nrev').textContent = n; $('ntot').textContent = total; $('naud').textContent = audF; $('ntaud').textContent = aud.length;
  $('t1').style.width = (100*n/total)+'%';
  marcarPendencias();
  const r = lista[pos];
  if (!r){ $('s-situacao').innerHTML='<h2>Nenhuma imagem neste filtro</h2><p class="crit">Escolha outro filtro no topo.</p>'; $('s-modelo').innerHTML=''; $('campos').innerHTML=''; $('mapa').innerHTML=''; $('ficha').innerHTML=''; $('grupo').hidden=true; return; }
  const oc = oculta(r), img = $('foto');
  if (img.dataset.src !== r.url){ img.dataset.src = r.url; img.src = r.url; $('palco').className = 'palco'; }
  img.onerror = () => { $('ficha').insertAdjacentHTML('afterbegin', '<span class="alerta-f">Não consegui abrir a imagem. O dataset continua no caminho do origem.json?</span>'); };
  $('selo').textContent = oc ? `nº ${r.n} · auditoria cega` : `nº ${r.n}`;
  $('selo').className = 'selo' + (cego(r) ? ' cego' : '');
  $('ficha').innerHTML = fichaTecnica(r);
  const gh = grupoDuplicatas(r); $('grupo').innerHTML = gh; $('grupo').hidden = !gh;
  document.querySelectorAll('.mini').forEach(e => e.onclick = () => { const q = POR_CAMINHO[e.dataset.c]; const i = q ? lista.indexOf(q) : -1;
    if (i >= 0){ pos = i; mostrar(); } else if (q) toast('Essa imagem não está no filtro atual'); else window.open(GRUPOS[r.grupo].find(m=>m.c===e.dataset.c).u, '_blank'); });
  $('s-situacao').innerHTML = secSituacao(r);
  $('s-modelo').innerHTML = secModelo(r);
  $('campos').innerHTML = secCampo(r,CAMPOS[0],1) + `<div class="duas">${secCampo(r,CAMPOS[1],2)}${secCampo(r,CAMPOS[2],3)}</div>` + secCampo(r,CAMPOS[3],4) + secCampo(r,CAMPOS[4],5);
  document.querySelectorAll('.opt').forEach(e => { e.onclick = () => marcar(e.dataset.c, e.dataset.v);
    e.onkeydown = ev => { if (ev.key===' ') { ev.preventDefault(); marcar(e.dataset.c, e.dataset.v); } }; });
  $('obs').value = reg(r).obs || '';
  $('ace').disabled = oc;
  $('ace').title = oc ? 'Indisponível na auditoria cega até você responder' : (MODO === 'ambiente' ? 'Enter: usa o ambiente sugerido pelo modelo' : 'Enter: preenche os campos vazios com a sugestão do modelo');
  $('mapa').innerHTML = lista.map((q,i) => `<i data-i="${i}" class="${feito(q)?'ok':''} ${cego(q)?'aud':''} ${i===pos?'cur':''}" title="nº ${q.n}"></i>`).join('');
  document.querySelectorAll('.mapa i').forEach(e => e.onclick = () => { pos = +e.dataset.i; mostrar(); });
}
function anotarObs(){ const r = lista[pos]; if (!r) return; reg(r).obs = $('obs').value; alteracoes++; salvar();
  marcarPendencias(); }
function marcarPendencias(){
  $('alt').innerHTML = alteracoes ? `<span class="pend">${alteracoes}</span>` : '';
  $('exp').title = alteracoes ? `${alteracoes} alterações ainda não exportadas. Estão salvas neste navegador, mas exporte para não perder.` : 'Baixa o CSV preenchido';
}
$('obs').oninput = anotarObs;
$('chips').innerHTML = OBS_RAPIDAS.map(t => `<span class="chip" role="button" tabindex="0" title="Acrescenta à observação">${esc(t)}</span>`).join('');
document.querySelectorAll('.chip').forEach(e => e.onclick = () => { const o = $('obs'); const t = e.textContent;
  if (!o.value.includes(t)) { o.value = o.value ? o.value.replace(/[;\s]*$/,'') + '; ' + t : t; anotarObs(); } });

function marcar(c, v){
  const r = lista[pos]; if (!r) return;
  const antes = feito(r), x = reg(r);
  x[c] = (x[c] === v) ? '' : v;
  if (cego(r) && !x.cego && feito(r)) x.cego = {ambiente:x.ambiente, fogo:x.fogo, fumaca:x.fumaca, quando:new Date().toISOString()};
  alteracoes++; salvar(); mostrar();
  if (!antes && feito(r)){
    const n = nRevisadas();
    if (n % 25 === 0) toast(`${n} revisadas. Exporte o CSV para guardar o trabalho.`);
    else toast(cego(r) ? 'Auditoria registrada. Veja a comparação com o modelo.' : 'Revisada');
    if ($('auto').checked && !cego(r)) { const alvo = pos; setTimeout(() => { if (pos === alvo) ir(1); }, 350); }
  }
}
function aceitar(){
  const r = lista[pos]; if (!r || oculta(r)) return;
  const x = reg(r);
  if (!x.ambiente) x.ambiente = r.amb_sug;
  if (MODO !== 'ambiente'){ if (!x.fogo) x.fogo = r.fogo_sug; if (!x.fumaca) x.fumaca = r.fum_sug; }
  alteracoes++; salvar(); toast('Sugestão aceita nos campos vazios'); ir(1);
}
function limpar(){
  const r = lista[pos]; if (!r) return;
  const c = reg(r).cego; delete st[r.caminho_relativo]; if (c) reg(r).cego = c;
  alteracoes++; salvar(); toast(c ? 'Marcações apagadas. A 1ª resposta da auditoria foi mantida.' : 'Marcações desta imagem apagadas'); mostrar();
}
function ir(d){ pos = Math.max(0, Math.min(lista.length-1, pos+d)); mostrar(); }
function proxNaoRevisada(){
  for (let k = 1; k <= lista.length; k++){ const i = (pos + k) % lista.length; if (!feito(lista[i])){ pos = i; mostrar(); return; } }
  toast('Todas as imagens deste filtro estão revisadas');
}
function lupa(){ const m = $('palco'); m.className = m.className.includes('zoom') ? 'palco' : 'palco zoom'; }

function wilson(k, n){ const z = 1.96, p = k/n, d = 1 + z*z/n;
  const c = (p + z*z/(2*n))/d, m = z*Math.sqrt(p*(1-p)/n + z*z/(4*n*n))/d; return [Math.max(0,c-m), Math.min(1,c+m)]; }
function resumo(){
  const rev = DATA.filter(feito);
  const cont = campo => { const a = {}; rev.forEach(r => { const v = reg(r)[campo] || (campo==='tipo'?'fotografia':''); if (v) a[v] = (a[v]||0)+1; }); return a; };
  const tab = (titulo, campo) => `<div><h4>${titulo}</h4><table>${Object.entries(cont(campo)).sort((a,b)=>b[1]-a[1]).map(([k,v])=>`<tr><td>${icone(campo,k)} ${lbl(k)}</td><td class="n">${v}</td></tr>`).join('') || '<tr><td>—</td></tr>'}</table></div>`;
  const aud = DATA.filter(r => cego(r) && reg(r).cego);
  const prec = f => { const k = aud.filter(f).length, n = aud.length; if (!n) return '<td class="n">—</td><td class="n">—</td>';
    const w = wilson(k,n); return `<td class="n">${(100*k/n).toFixed(0)}% (${k}/${n})</td><td class="n">${(100*w[0]).toFixed(0)} a ${(100*w[1]).toFixed(0)}%</td>`; };
  const mot = [...new Set(DATA.flatMap(motivos))];
  const nf = rev.filter(r => /non_fire/i.test(r.classe_original) && reg(r).fogo==='sim').length;
  const fn = rev.filter(r => !/non_fire/i.test(r.classe_original) && reg(r).fogo==='nao').length;
  $('cx').innerHTML = `<h3>Resumo da revisão</h3>
   <p><b>${rev.length}</b> de ${DATA.length} imagens revisadas. Auditoria cega: <b>${aud.length}</b> de ${DATA.filter(cego).length}.</p>
   <h4>Progresso por motivo</h4><table><tr><th>Motivo</th><th class="n">Revisadas</th><th class="n">Total</th></tr>
    ${mot.map(m => { const t = DATA.filter(r=>motivos(r).includes(m)); return `<tr><td>${(MOTIVO[m]||[m])[0]}</td><td class="n">${t.filter(feito).length}</td><td class="n">${t.length}</td></tr>`; }).join('')}</table>
   <div class="colunas">${tab('Ambiente','ambiente')}${tab('Fogo (chama visível)','fogo')}${tab('Fumaça','fumaca')}</div>
   <div class="colunas">${tab('Tipo de imagem','tipo')}${tab('Câmera','camera')}<div></div></div>
   <h4>Rótulos da pasta que parecem errados (entre as revisadas)</h4><table>
    <tr><td>Pasta sem fogo, mas com chama visível</td><td class="n">${nf}</td></tr><tr><td>Pasta com fogo, mas sem chama visível</td><td class="n">${fn}</td></tr></table>
   <h4>Acerto do modelo na auditoria cega</h4><table><tr><th>Campo</th><th class="n">Acerto</th><th class="n">Intervalo de 95% (Wilson)</th></tr>
    <tr><td>Ambiente</td>${prec(r=>reg(r).cego.ambiente===r.amb_sug)}</tr>
    <tr><td>Fogo</td>${prec(r=>reg(r).cego.fogo===r.fogo_sug)}</tr>
    <tr><td>Fumaça</td>${prec(r=>reg(r).cego.fumaca===r.fum_sug)}</tr></table>
   <p class="nota">Prévia. O número oficial sai do script 05c, a partir do CSV exportado.</p>
   <div style="display:flex;gap:8px;justify-content:space-between;margin-top:14px"><button id="zer">Apagar todas as marcações deste navegador</button><button id="fec" class="forte">Fechar</button></div>`;
  $('modal').className = 'on'; $('fec').focus();
  $('fec').onclick = () => { $('modal').className = ''; };
  $('zer').onclick = () => { if (confirm('Apagar TODAS as marcações salvas neste navegador? Exporte o CSV antes se quiser guardá-las.') && confirm('Tem certeza? Isso não pode ser desfeito.')) { st = {}; salvar(); alteracoes = 0; $('modal').className=''; aplicar(); toast('Marcações apagadas'); } };
}
function ajuda(){
  const linhas = [['1 a 7','Ambiente'],['Q  W  E','Fogo: sim, não, incerto'],['A  S  D','Fumaça: sim, não, incerto'],['Z  X  C','Tipo: fotografia, sintética, sensor'],
    ['T  Y  U  I  O','Câmera: satélite, drone, vigilância, do chão, incerto'],['←  →','Imagem anterior e próxima'],['N','Próxima imagem não revisada'],
    ['Enter','Aceitar a sugestão nos campos vazios (bloqueado na auditoria cega)'],['Backspace','Limpar as marcações desta imagem'],['L','Ver em tamanho real'],['?','Esta ajuda'],['Esc','Fechar esta janela']];
  $('cx').innerHTML = `<h3>Atalhos de teclado</h3><table>${linhas.map(([k,d])=>`<tr><td style="white-space:nowrap">${k.split('  ').map(t=>`<kbd>${t}</kbd>`).join(' ')}</td><td>${d}</td></tr>`).join('')}</table>
   <h4>Como funciona a auditoria cega</h4><p style="font-size:13px;color:var(--mudo)">Nas imagens de auditoria, a pasta, o caminho, o grupo e a sugestão ficam ocultos. Na primeira vez que você completa ambiente, fogo e fumaça, essa resposta é gravada como “cega” e é a única usada para medir o acerto do modelo. Correções depois disso mudam só o rótulo final.</p>
   <div style="text-align:right;margin-top:12px"><button id="fec" class="forte">Fechar</button></div>`;
  $('modal').className = 'on'; $('fec').focus(); $('fec').onclick = () => { $('modal').className = ''; };
}
$('modal').onclick = e => { if (e.target.id === 'modal') $('modal').className = ''; };
$('foto').onclick = lupa;
$('ant').onclick = () => ir(-1); $('prox').onclick = () => ir(1); $('nr').onclick = proxNaoRevisada; $('ace').onclick = aceitar; $('lim').onclick = limpar;
$('res').onclick = resumo; $('aj').onclick = ajuda;
$('filtro').onchange = () => { pos = 0; aplicar(); $('filtro').blur(); };
$('ir').onchange = e => { const n = parseInt(e.target.value,10); const i = lista.findIndex(r => r.n===n); if (i>=0){pos=i; mostrar();} else toast('nº '+n+' não está neste filtro'); e.target.blur(); };
document.addEventListener('click', e => { const b = e.target.closest && e.target.closest('button'); if (b) b.blur(); });
document.addEventListener('keydown', e => {
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  const t = e.target;
  if (t.tagName === 'TEXTAREA' || (t.tagName === 'INPUT' && t.type === 'number')) return;
  if ($('modal').className === 'on'){ if (e.key === 'Escape') $('modal').className = ''; return; }
  if (t.tagName === 'SELECT' || t.tagName === 'BUTTON' || t.tagName === 'INPUT') t.blur();
  const k = e.key.toLowerCase();
  const tratar = f => { e.preventDefault(); f(); };
  if (e.key==='ArrowRight') return tratar(() => ir(1));
  if (e.key==='ArrowLeft') return tratar(() => ir(-1));
  if (e.key==='Enter') return tratar(aceitar);
  if (e.key==='Backspace' || e.key==='Delete') return tratar(limpar);
  if (k==='n') return tratar(proxNaoRevisada);
  if (k==='l') return tratar(lupa);
  if (e.key==='?') return tratar(ajuda);
  for (const c of CAMPOS) for (const [v,tc] of c.op) if (k===tc) return tratar(() => marcar(c.id, v));
});

const csv = s => '"' + String(s ?? '').replace(/"/g,'""') + '"';
function exportar(){
  const cols = ['n','caminho_relativo','classe_original','motivos_revisao','ambiente_sugerido','fogo_sugerido','fumaca_sugerida',
                'ambiente_confirmado','fogo_confirmado','fumaca_confirmada','tipo_imagem','camera_confirmada','observacao','revisado',
                'ambiente_cego','fogo_cego','fumaca_cego','quando_cego'];
  const linhas = DATA.map(r => { const x = reg(r), c = x.cego || {}; return [r.n,r.caminho_relativo,r.classe_original,r.motivos,r.amb_sug,r.fogo_sug,r.fum_sug,
      x.ambiente||'',x.fogo||'',x.fumaca||'',x.tipo||(feito(r)?'fotografia':''),x.camera||'',x.obs||'',feito(r)?'sim':'nao',
      c.ambiente||'',c.fogo||'',c.fumaca||'',c.quando||''].map(csv).join(','); });
  const blob = new Blob([cols.join(',')+'\r\n'+linhas.join('\r\n')+'\r\n'], {type:'text/csv;charset=utf-8'});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = EXPORTAR_COMO;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  alteracoes = 0; mostrar(); toast(EXPORTAR_COMO + ' exportado. Guarde em relatorios/05_sugestoes/');
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
  const t = parseCSV((await f.text()).replace(/^﻿/,'')); const h = t.shift(); const ix = n => h.indexOf(n);
  let c = 0;
  for (const l of t){ const g = n => (ix(n) >= 0 ? (l[ix(n)] || '') : ''); const k = g('caminho_relativo'); if (!k) continue;
    const x = {ambiente:g('ambiente_confirmado'),fogo:g('fogo_confirmado'),fumaca:g('fumaca_confirmada'),
               tipo:g('tipo_imagem'),camera:g('camera_confirmada'),obs:g('observacao')};
    if (g('ambiente_cego') || g('fogo_cego') || g('fumaca_cego'))
      x.cego = {ambiente:g('ambiente_cego'),fogo:g('fogo_cego'),fumaca:g('fumaca_cego'),quando:g('quando_cego')};
    st[k] = x; c++; }
  salvar(); aplicar(); toast(c + ' linhas importadas'); e.target.value = '';
};
$('dsnome').textContent = MODO === 'ambiente' ? '2ª revisão: só ambiente' : DATASET;
if (MODO === 'ambiente'){
  document.title = 'Revisão de ambiente – Ignis Alert';
  $('ace').textContent = 'Aceitar o ambiente sugerido';
}
if (!DATA.some(cego)){ $('caud').hidden = true; document.querySelector('.legenda-mapa span:nth-child(3)').hidden = true; }
aplicar();
window.addEventListener('beforeunload', e => { if (alteracoes) { e.preventDefault(); e.returnValue = ''; } });
</script></body></html>
"""


def ler(caminho):
    with open(caminho, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def ler_opcional(caminho):
    return ler(caminho) if Path(caminho).exists() else []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--origem", default="relatorios/01_origem/origem.json")
    ap.add_argument("--validacao", default="relatorios/02_validacao/validacao.csv")
    ap.add_argument("--grupos", default="relatorios/03_duplicatas/imagem_grupo.csv")
    ap.add_argument("--pendentes", default="relatorios/04_divisao/pendentes.csv")
    ap.add_argument("--modo", choices=["completo", "ambiente"], default="completo",
                    help="ambiente = 2ª revisão, só o ambiente é obrigatório (lista do 05c)")
    ap.add_argument("--revisao", help="padrão: revisao.csv (completo) ou revisao_ambiente.csv (ambiente)")
    ap.add_argument("--sugestoes", default="relatorios/05_sugestoes/sugestoes.csv")
    ap.add_argument("--metadados", default="relatorios/05_sugestoes/metadados.json")
    ap.add_argument("--saida", help="padrão: revisao.html (completo) ou revisao_ambiente.html (ambiente)")
    a = ap.parse_args()
    base = "relatorios/05_sugestoes/" + ("revisao_ambiente" if a.modo == "ambiente" else "revisao")
    a.revisao = a.revisao or base + ".csv"
    a.saida = a.saida or base + ".html"
    exportar_como = Path(base).name + "_preenchida.csv"

    origem = json.loads(Path(a.origem).read_text(encoding="utf-8"))
    raiz = Path(origem["caminho_local"])
    sug = {r["caminho_relativo"]: r for r in ler(a.sugestoes)}
    val = {r["caminho_relativo"]: r for r in ler_opcional(a.validacao)}
    pend = {r["caminho_relativo"]: r["motivo"] for r in ler_opcional(a.pendentes)}
    lim = dict(LIM_PADRAO)
    if Path(a.metadados).exists():
        lim.update(json.loads(Path(a.metadados).read_text(encoding="utf-8")).get("limiares", {}))

    membros = defaultdict(list)
    for r in ler_opcional(a.grupos):
        membros[r["id_grupo"]].append(r["caminho_relativo"])

    revisao = ler(a.revisao)
    num = {r["caminho_relativo"]: int(r["n"]) for r in revisao}
    dados, grupos_usados = [], {}
    for r in revisao:
        s, v = sug[r["caminho_relativo"]], val.get(r["caminho_relativo"], {})
        dados.append({
            "n": int(r["n"]), "caminho_relativo": r["caminho_relativo"], "classe_original": r["classe_original"],
            "motivos": r["motivos_revisao"], "url": (raiz / r["caminho_relativo"]).as_uri(),
            "amb_sug": s["ambiente_sugerido"], "amb_top1": s["amb_top1"], "amb_conf": s["amb_conf"],
            "amb_top2": s["amb_top2"], "amb_margem": s["amb_margem"],
            "fogo_sug": s["fogo_sugerido"], "fogo_p": s["fogo_prob"],
            "fum_sug": s["fumaca_sugerida"], "fum_p": s["fumaca_prob"],
            "cam_sug": s["camera_sugerida_fraca"], "cam_conf": s["camera_conf"],
            "split": s.get("split", ""), "grupo": s["id_grupo"], "pendente": pend.get(r["caminho_relativo"], ""),
            "largura": v.get("largura", ""), "altura": v.get("altura", ""), "formato": v.get("formato_real", ""),
            "modo": v.get("modo_cor", ""), "flags": v.get("flags", "")})
        g = s["id_grupo"]
        if len(membros.get(g, [])) > 1 and g not in grupos_usados:
            grupos_usados[g] = [{"c": c, "u": (raiz / c).as_uri(), "n": num.get(c)} for c in sorted(membros[g])]

    def js(obj):
        return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")
    nome_ds = origem.get("dataset_ref", "")
    if origem.get("versao_kaggle"):
        nome_ds += f" v{origem['versao_kaggle']}"
    html = (HTML.replace("__DATA__", js(dados)).replace("__GRUPOS__", js(grupos_usados))
                .replace("__LIM__", js(lim)).replace("__DATASET__", js(nome_ds))
                .replace("__MODO__", js(a.modo)).replace("__EXPORTAR_COMO__", js(exportar_como)))
    Path(a.saida).write_text(html, encoding="utf-8")
    cegas = sum(d["motivos"] == "auditoria" for d in dados)
    print(f"Página gerada: {a.saida}\nImagens: {len(dados)} (das quais {cegas} cegas, de auditoria)")
    print(f"Grupos de duplicatas mostrados: {len(grupos_usados)} | limiares: {lim}")
    print(f"Modo: {a.modo} | o botão Exportar baixa: {exportar_como}")
    print("Abra o arquivo no Chrome ou Edge (duplo clique).")


if __name__ == "__main__":
    main()
