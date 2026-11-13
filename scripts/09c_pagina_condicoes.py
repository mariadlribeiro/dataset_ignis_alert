#!/usr/bin/env python3
"""
Etapa 9c - Gera a PÁGINA DE REVISÃO DAS CONDIÇÕES (HTML local): ponto de vista e distância do fogo.
(A iluminação, clara/média/escura, é medida automaticamente na 9a e aparece só como informação.)

Abra o arquivo gerado (relatorios/09_condicoes/revisao_condicoes.html) no Chrome ou Edge.
  * mostra cada imagem grande, o ambiente e o fogo já decididos na Etapa 5, as medidas automáticas da 9a
    (brilho, nitidez) e a sugestão do CLIP da 9b;
  * critérios de cada opção ficam visíveis ao lado das opções;
  * linhas de AUDITORIA são cegas: a sugestão e o caminho só aparecem depois que você responde. A PRIMEIRA
    resposta fica gravada em *_cego e não muda se você corrigir depois;
  * a distância do fogo só é pedida em imagens com fogo;
  * 14 perguntas em dois blocos. A CENA: ponto de vista, hora do dia, céu, vegetação, água, pessoas, veículos,
    texto/marca d'água e o que pode confundir. O FOGO (só com fogo): tipo, distância, focos, cor das chamas, encoberto;
  * as teclas 1 a 6 respondem a pergunta destacada, que avança sozinha; setas ↑ ↓ trocam a pergunta;
  * lupa que acompanha o mouse (tecla O) e tela cheia (tecla P); ficha com as medidas automáticas da 9a;
  * cada opção de ponto de vista e distância é um cartão com fotos de exemplo; o palpite do modelo fica escondido até você pedir (tecla M); e só dá para marcar depois de olhar a imagem por 3 segundos
    (o tempo de cada resposta vai para o CSV, colunas segundos e segundos_cego);
  * o progresso fica salvo no navegador (separado da página da Etapa 5); o botão "Exportar CSV" baixa
    revisao_condicoes_preenchida.csv;
  * nada no dataset é alterado.

Uso:  python scripts/09c_pagina_condicoes.py
      python scripts/09c_pagina_condicoes.py --revisao relatorios/09_condicoes/revisao_condicoes_2.csv   # 2ª volta (09d)
"""
import argparse, csv, json
from pathlib import Path

LIM_PADRAO = {"conf_min": 0.50, "margem_min": 0.15}
ORDEM_ATR = ("ponto_vista", "hora_dia", "ceu", "vegetacao", "agua", "pessoas", "veiculos", "texto", "confusor",
             "tipo_fogo", "distancia_fogo", "focos", "cor_chamas", "encoberto")

# Exemplos de referência para cada opção. Todos vêm das auditorias descartadas (tentativas 1 e 2),
# então NUNCA aparecem na lista a revisar. Conferidos visualmente em 11/11/2026.
EXEMPLOS = {
    "ponto_vista": {"chao": ["fire_images/fire.187.png", "fire_images/fire.130.png"], "elevado": ["non_fire_images/non_fire.44.png"],
                    "aereo": ["fire_images/fire.376.png", "non_fire_images/non_fire.209.png"], "satelite": ["fire_images/fire.311.png"]},
    "distancia_fogo": {"perto": ["fire_images/fire.220.png", "fire_images/fire.148.png"], "medio": ["fire_images/fire.130.png", "fire_images/fire.134.png"],
                       "distante": ["fire_images/fire.405.png", "fire_images/fire.202.png"]},
}

HTML = r"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>Condições das imagens – Ignis Alert</title>
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
.exemplos{display:grid;grid-template-columns:repeat(auto-fill,minmax(118px,1fr));gap:8px;margin-top:10px}
.exemplo{font-size:11.5px;color:var(--mudo)}.exemplo b{display:block;color:var(--tinta);font-size:12px;margin-bottom:3px}
.exemplo .fotos{display:flex;gap:4px}.exemplo img{width:56px;height:42px;object-fit:cover;border-radius:4px;cursor:zoom-in;background:var(--palco)}
.espera{font-size:12.5px;color:var(--brasa);margin-top:6px;font-weight:600}
.sec.curta{padding:8px 0 9px}.sec.curta h2{font-size:14px}
.sec.ativa{background:var(--brasa-suave);box-shadow:inset 4px 0 0 var(--brasa);margin:0 -16px;padding-left:16px;padding-right:16px}
.grupo-t{margin:14px 0 2px;font-size:12px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--brasa)}
.sw{display:inline-block;width:14px;height:14px;border-radius:3px;margin-left:3px;vertical-align:-2px;border:1px solid #0002}
.lente{position:absolute;width:240px;height:240px;border-radius:50%;border:3px solid #fff;box-shadow:0 4px 18px #0009;pointer-events:none;background-repeat:no-repeat;display:none;z-index:5}
.palco:fullscreen{border-radius:0}
.pergunta{font-size:17px;font-weight:700;margin:2px 0 2px;letter-spacing:-.2px}
.tiles{display:grid;grid-template-columns:repeat(var(--n),1fr);gap:7px;margin-top:8px}
.incerto-linha{margin-top:7px;display:flex;align-items:center;gap:8px;font-size:12px;color:var(--mudo)}
.tile{display:flex;flex-direction:column;border:2px solid var(--linha);border-radius:10px;background:var(--folha);cursor:pointer;overflow:hidden;user-select:none;position:relative}
.tile:hover{border-color:var(--tinta)} .tile:focus-visible{outline:3px solid var(--foco);outline-offset:1px}
.tile .fotos{display:flex;height:64px;background:var(--palco);gap:2px}
.tile .fotos img{flex:1;min-width:0;height:64px;object-fit:cover;display:block}
.tile .semfoto{height:74px;display:grid;place-items:center;font-size:28px;background:var(--linha2)}
.tile .rot{display:flex;align-items:center;justify-content:space-between;gap:4px;padding:5px 7px;font-size:13px;font-weight:650}
.tile .rot kbd{font-size:11px}
.tile.on{border-color:var(--tinta);box-shadow:0 0 0 2px var(--tinta)} .tile.on .rot{background:var(--tinta);color:var(--folha)}
.tile.on .rot kbd{background:transparent;color:var(--folha);border-color:var(--folha)}
.tile.sug:not(.on){border-style:dashed;border-color:var(--fumo)}
.tile .palpite{position:absolute;top:5px;right:5px;background:#000b;color:#fff;font-size:10.5px;padding:1px 6px;border-radius:4px}
.tile .ver{position:absolute;top:5px;left:5px;background:#fffd;color:#1e2421;font-size:11px;padding:1px 6px;border-radius:4px;text-decoration:none;opacity:0;transition:opacity .15s}
.tile:hover .ver{opacity:1}
.btn-palpite{width:100%;justify-content:center;border-style:dashed;color:var(--mudo)}
.relogio{position:absolute;left:0;right:0;bottom:0;height:6px;background:#ffffff1f;pointer-events:none}
.relogio i{display:block;height:100%;width:0;background:var(--brasa)}
.relogio.rodando i{animation:enche 3s linear forwards}
.relogio span{position:absolute;right:10px;bottom:12px;color:#fff;font-size:12.5px;background:#000b;padding:3px 9px;border-radius:5px;white-space:nowrap}
.relogio.pronto{opacity:0;transition:opacity .5s .4s}
@keyframes enche{to{width:100%}}
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
 <div class="marca">Condições das imagens<small id="dsnome"></small></div>
 <div class="progresso">
  <div class="rot"><span><b id="nrev">0</b> de <span id="ntot"></span> revisadas</span><span id="caud">auditoria cega <b id="naud">0</b> de <span id="ntaud"></span></span></div>
  <div class="trilha"><i id="t1" style="background:var(--mata)"></i></div>
 </div>
 <div class="ferr">
  <select id="filtro" title="Mostrar só um motivo de revisão"></select>
  <label title="Pula para a próxima imagem assim que os campos obrigatórios estiverem marcados" style="display:flex;gap:5px;align-items:center;font-size:13px"><input type="checkbox" id="auto" checked> Avançar<span class="curto"> sozinho</span></label>
  <label style="font-size:13px"><span class="curto">Ir para </span>nº <input id="ir" type="number" min="1" style="width:64px"></label>
  <button id="res">Resumo</button>
  <button id="imp" title="Carrega um CSV exportado antes">Importar</button>
  <button id="exp" class="forte" title="Baixa o CSV preenchido">Exportar CSV<span id="alt"></span></button>
  <button id="aj" title="Atalhos de teclado (?)" aria-label="Atalhos de teclado">?</button>
  <input id="arq" type="file" accept=".csv" hidden>
 </div>
</header>
<main>
 <section class="esq">
  <div class="palco" id="palco"><span class="selo" id="selo"></span><img id="foto" alt="imagem em revisão" title="Clique ou tecla L para ver em tamanho real"><div class="lente" id="lente"></div><div class="relogio" id="relogio"><i></i><span id="relogio-t">Observe a imagem…</span></div></div>
  <div class="ficha" id="ficha"></div>
  <div class="mapa" id="mapa"></div>
  <div class="legenda-mapa"><span><i style="background:var(--linha)"></i>pendente</span><span><i style="background:var(--mata)"></i>revisada</span><span><i style="box-shadow:inset 0 0 0 2px var(--brasa)"></i>auditoria cega</span><span>clique num quadrado para ir até a imagem</span></div>
 </section>
 <section class="dir">
  <div class="rolagem">
   <div class="sec" id="s-situacao"></div>
   <div id="campos"></div>
   <div class="sec" id="s-modelo"></div>
   <div class="sec">
    <h2>Observação <span class="dica">vai para o CSV</span></h2>
    <div class="chips" id="chips"></div>
    <textarea id="obs" placeholder="Algo que explique a decisão: fogo cortado pela borda, fumaça cobre o fogo…"></textarea>
   </div>
  </div>
  <div class="acoes">
   <button id="ant" title="Seta para a esquerda">← Anterior</button>
   <button id="prox" title="Seta para a direita">Próxima →</button>
   <button id="nr" title="Tecla N">Próxima pendente</button>
   <button id="lim" title="Backspace: apaga as marcações desta imagem">Limpar marcações</button>
   <button id="ace" class="forte larga" title="Enter: preenche os campos vazios com o palpite do modelo (só com o palpite à mostra)">Aceitar o palpite nos campos vazios</button>
  </div>
 </section>
</main>
<div id="toast" role="status"></div>
<div id="modal"><div class="cx" id="cx" role="dialog" aria-modal="true"></div></div>
<script>
const DATA = __DATA__;
const LIM = __LIM__;
const DATASET = __DATASET__;
const EXPORTAR_COMO = __EXPORTAR_COMO__;
const ATRS = __ATRS__;
const KEY = 'ignis_condicoes_v2';
const EXEMPLOS = __EXEMPLOS__;
const T_MIN = 3000;  // ms: tempo mínimo olhando a imagem antes de poder marcar
let mostradaEm = Date.now();
let ativa = 0;   // índice (em perguntasDe(r)) da pergunta que recebe as teclas 1-6
const perguntasDe = r => CAMPOS.filter(c => aplica(r,c));
function proximaAtiva(r){ const qs = perguntasDe(r), x = reg(r); const i = qs.findIndex(c => !x[c.id]); ativa = i >= 0 ? i : Math.max(0, qs.length-1); }
let verPalpite = false;
try { verPalpite = localStorage.getItem(KEY + '_palpite') === '1'; } catch(e) {}
const palpiteVisivel = r => !oculta(r) && (verPalpite || cego(r));

const LABEL = {dia:'Dia',noite:'Noite',entardecer:'Entardecer',contraluz:'Contraluz',chao:'Do chão',elevado:'Elevado',aereo:'Aéreo',satelite:'Satélite',
  perto:'Perto',medio:'Médio',distante:'Distante',incerto:'Incerto',nao_se_aplica:'Não se aplica',
  floresta:'Floresta',cidade:'Cidade',casa:'Casa',predios:'Prédios',flores_jardins:'Flores e jardins',outros:'Outros',
  sim:'Sim',nao:'Não',nenhum:'Nenhum',noite:'Noite',entardecer:'Entardecer ou amanhecer',floresta_densa:'Floresta densa',campo:'Campo, cerrado ou pasto',urbana:'Urbana (jardim, árvores de rua)',sem_vegetacao:'Sem vegetação',
  florestal:'Incêndio florestal',estrutura:'Prédio ou casa',veiculo:'Veículo',controlado:'Controlado (fogueira, vela, fogão)',outro:'Outro',um:'Um foco',varios:'Vários focos',
  amarela:'Amarela',laranja:'Laranja',vermelha:'Vermelha',azulada:'Azulada',mista:'Mista',fumaca:'Sim, por fumaça',vegetacao:'Sim, por vegetação',pessoas_objetos:'Sim, por pessoas ou objetos',por_do_sol:'Pôr do sol',luz_artificial:'Luz artificial',reflexo:'Reflexo',neblina:'Neblina',
  treino:'treino',validacao:'validação',teste:'teste'};
const ICON = {dia:'☀️',noite:'🌙',entardecer:'🌅',contraluz:'🌄',chao:'🧍',elevado:'🗼',aereo:'🚁',satelite:'🛰️',perto:'🔥',medio:'🏘️',distante:'🏔️',incerto:'❔',sim:'✔',nao:'✖',floresta_densa:'🌲',campo:'🌾',urbana:'🏙️',sem_vegetacao:'🧱',florestal:'🌲',estrutura:'🏠',veiculo:'🚗',controlado:'🕯️',outro:'·',um:'1',varios:'⁂',amarela:'🟡',laranja:'🟠',vermelha:'🔴',azulada:'🔵',mista:'🎨',fumaca:'💨',vegetacao:'🌿',pessoas_objetos:'🧍',nenhum:'·',por_do_sol:'🌅',luz_artificial:'💡',reflexo:'🪞',neblina:'🌫️'};
const DEF = {
 ponto_vista:{chao:'Pessoa no chão, na altura dos olhos.', elevado:'De um ponto alto (morro, torre, prédio, câmera fixa), olhando em diagonal para baixo.',
   aereo:'De cima, de drone, avião ou helicóptero.', satelite:'Vista do espaço, de cima para baixo.', incerto:'Não dá para dizer.'},
 distancia_fogo:{perto:'As chamas ocupam boa parte da imagem; dá para ver a forma das labaredas.',
   medio:'O fogo é visível com o entorno: o prédio, as árvores, a rua.', distante:'O fogo é um ponto ou faixa pequena na paisagem; muitas vezes se vê mais fumaça que chama.',
   incerto:'Não dá para dizer.'},
 pessoas:{sim:'Há pelo menos uma pessoa visível, mesmo pequena ou em silhueta (bombeiro, morador, curioso).', nao:'Nenhuma pessoa visível.'},
 veiculos:{sim:'Há algum veículo visível: carro, caminhão, viatura, helicóptero, avião.', nao:'Nenhum veículo visível.'},
 texto:{sim:'Há texto, legenda, logotipo ou marca d\'água desenhado SOBRE a imagem.', nao:'Sem texto sobreposto (placas e letreiros da própria cena não contam).'},
 hora_dia:{dia:'Luz do sol ou céu de dia, mesmo nublado.', noite:'Céu escuro; a luz vem do fogo ou de lâmpadas.', entardecer:'Sol baixo, céu alaranjado ou azul-escuro de fim de tarde ou amanhecer.', incerto:'Não dá para dizer (recorte fechado, fumaça cobre tudo).'},
 ceu:{sim:'Aparece algum pedaço de céu (mesmo coberto de fumaça).', nao:'Nenhum céu visível.'},
 vegetacao:{floresta_densa:'Muitas árvores juntas, mata fechada.', campo:'Capim, pasto, cerrado, arbustos baixos.', urbana:'Árvores de rua, jardim, gramado de casa ou praça.', sem_vegetacao:'Nenhuma planta visível.'},
 agua:{sim:'Rio, lago, mar, poça ou jato de água de mangueira visível.', nao:'Nenhuma água visível.'},
 tipo_fogo:{florestal:'Fogo em mata ou floresta.', estrutura:'Fogo em prédio, casa, galpão ou outra construção.', veiculo:'Fogo em carro, caminhão, ônibus.', campo:'Fogo em capim, pasto, plantação ou terreno.', controlado:'Fogo pequeno e intencional: fogueira, vela, fogão, churrasqueira, lareira.', outro:'Nenhum dos anteriores (lixo, poste, explosão…).'},
 focos:{um:'Um fogo só, contínuo.', varios:'Dois ou mais focos separados.'},
 cor_chamas:{amarela:'Chamas principalmente amarelas ou brancas.', laranja:'Chamas principalmente laranja.', vermelha:'Chamas principalmente vermelhas ou escuras.', azulada:'Chama azul (gás).', mista:'Várias cores sem uma principal.'},
 encoberto:{nao:'O fogo aparece inteiro, sem nada na frente.', fumaca:'Fumaça cobre parte do fogo.', vegetacao:'Árvores ou mato escondem parte do fogo.', pessoas_objetos:'Pessoas, veículos ou objetos na frente do fogo.'},
 confusor:{nenhum:'Nada na imagem parece fogo sem ser fogo, nem esconde o fogo.', por_do_sol:'Céu alaranjado de pôr do sol ou nascer do sol.',
   luz_artificial:'Lâmpadas, postes, faróis ou letreiros com luz laranja ou amarela.', reflexo:'Fogo ou luz refletidos em água, vidro ou metal.',
   neblina:'Neblina, névoa ou fumaça clara que deixa a cena turva.'}
};
const CAMPOS_TODOS = [
 // A CENA
 {id:'ponto_vista',grupo:'cena',nome:'Ponto de vista',curto:'Vista',pergunta:'De onde a foto foi tirada?',crit:'Compare com as fotos de exemplo de cada opção.',tiles:true,op:['chao','elevado','aereo','satelite','incerto']},
 {id:'hora_dia',grupo:'cena',nome:'Hora do dia',curto:'Hora',tipo:'chips',pergunta:'Que hora do dia parece ser?',op:['dia','noite','entardecer','incerto']},
 {id:'ceu',grupo:'cena',nome:'Céu',curto:'Céu',tipo:'chips',pergunta:'Aparece céu na imagem?',op:['sim','nao']},
 {id:'vegetacao',grupo:'cena',nome:'Vegetação',curto:'Vegetação',tipo:'chips',pergunta:'Que vegetação aparece?',op:['floresta_densa','campo','urbana','sem_vegetacao']},
 {id:'agua',grupo:'cena',nome:'Água',curto:'Água',tipo:'chips',pergunta:'Aparece água (rio, lago, mar, jato de mangueira)?',op:['sim','nao']},
 {id:'pessoas',grupo:'cena',nome:'Pessoas',curto:'Pessoas',tipo:'chips',pergunta:'Aparece alguma pessoa?',op:['sim','nao']},
 {id:'veiculos',grupo:'cena',nome:'Veículos',curto:'Veículos',tipo:'chips',pergunta:'Aparece algum veículo?',op:['sim','nao']},
 {id:'texto',grupo:'cena',nome:'Texto ou marca d\'água',curto:'Texto',tipo:'chips',pergunta:'Tem texto ou marca d\'água sobre a imagem?',op:['sim','nao']},
 {id:'confusor',grupo:'cena',nome:'O que pode confundir',curto:'Confunde',tipo:'chips',pergunta:'Tem algo que parece fogo sem ser, ou que esconde o fogo?',op:['nenhum','por_do_sol','luz_artificial','reflexo','neblina']},
 // O FOGO (só imagens com fogo)
 {id:'tipo_fogo',grupo:'fogo',soFogo:true,nome:'Tipo de fogo',curto:'Tipo',tipo:'chips',pergunta:'Que tipo de fogo é?',op:['florestal','estrutura','veiculo','campo','controlado','outro']},
 {id:'distancia_fogo',grupo:'fogo',soFogo:true,nome:'Distância do fogo',curto:'Distância',pergunta:'Quanto o fogo ocupa da imagem?',crit:'Perto: chamas enchem a foto. Médio: fogo e o que está em volta. Distante: fogo pequeno, longe.',tiles:true,op:['perto','medio','distante','incerto']},
 {id:'focos',grupo:'fogo',soFogo:true,nome:'Focos',curto:'Focos',tipo:'chips',pergunta:'Quantos focos de fogo separados?',op:['um','varios']},
 {id:'cor_chamas',grupo:'fogo',soFogo:true,nome:'Cor das chamas',curto:'Cor',tipo:'chips',pergunta:'Qual a cor principal das chamas?',op:['amarela','laranja','vermelha','azulada','mista']},
 {id:'encoberto',grupo:'fogo',soFogo:true,nome:'Fogo encoberto',curto:'Encoberto',tipo:'chips',pergunta:'O fogo está parcialmente escondido?',op:['nao','fumaca','vegetacao','pessoas_objetos']}
].map(c => ({...c, op: c.op.map((v,i) => [v, String(i+1)])}));
const CAMPOS = CAMPOS_TODOS.filter(c => ATRS.includes(c.id));
const aplica = (r,c) => !c.soFogo || r.fogo === 'sim';
const obrig = r => CAMPOS.filter(c => aplica(r,c)).map(c => c.id);
const MOTIVO = {
 auditoria:['Auditoria cega','Amostra aleatória das imagens em que o modelo estava seguro. Responda sem ver a sugestão: serve para medir quanto ele acerta.'],
 ponto_vista_incerto:['Ponto de vista incerto','O modelo não teve confiança ou margem suficiente.'],
 distancia_fogo_incerto:['Distância incerta','O modelo não teve confiança ou margem suficiente.'],
 pessoas_incerto:['Pessoas: modelo em dúvida',''], veiculos_incerto:['Veículos: modelo em dúvida',''], texto_incerto:['Texto: modelo em dúvida',''],
 confusor_incerto:['Confusão: modelo em dúvida',''],
 hora_dia_incerto:['Hora do dia: modelo em dúvida',''], ceu_incerto:['Céu: modelo em dúvida',''], vegetacao_incerto:['Vegetação: modelo em dúvida',''],
 agua_incerto:['Água: modelo em dúvida',''], tipo_fogo_incerto:['Tipo de fogo: modelo em dúvida',''],
 completa:['Revisão completa','Todas as imagens são revisadas à mão; o palpite do modelo é só uma referência.'],
 nao_confiavel:['Sugestão não confiável','O modelo estava seguro, mas a auditoria mostrou que ele erra muito nesta sugestão.']
};
const OBS_RAPIDAS = ['fogo cortado pela borda','várias fontes de luz','imagem muito escura','reflexo','fumaça cobre o fogo','recorte muito fechado'];

let st = {};
try { st = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch(e) {}
let alteracoes = 0, lista = [], pos = 0;
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const salvar = () => { try { localStorage.setItem(KEY, JSON.stringify(st)); } catch(e) {} };
const reg = r => (st[r.caminho] = st[r.caminho] || {});
const feito = r => obrig(r).every(k => reg(r)[k]);
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
    `<option value="__impar">Revisora 1: nº ímpares (${DATA.filter(r => r.n % 2 === 1 && feito(r)).length}/${DATA.filter(r => r.n % 2 === 1).length})</option><option value="__par">Revisora 2: nº pares (${DATA.filter(r => r.n % 2 === 0 && feito(r)).length}/${DATA.filter(r => r.n % 2 === 0).length})</option>` +
    mot.map(m => { const t = DATA.filter(r => motivos(r).includes(m)); return `<option value="${m}">${(MOTIVO[m]||[m])[0]} (${t.filter(feito).length}/${t.length})</option>`; }).join('');
  $('filtro').value = atual;
}
function aplicar(){
  const v = $('filtro').value;
  lista = DATA.filter(r => !v || (v==='__falta' ? !feito(r) : v==='__impar' ? r.n % 2 === 1 : v==='__par' ? r.n % 2 === 0 : motivos(r).includes(v)));
  pos = Math.min(pos, Math.max(lista.length-1,0)); mostrar();
}
function secSituacao(r){
  const x = reg(r), qs = perguntasDe(r), falta = qs.filter(c => !x[c.id]).length;
  let h = `<h2>Imagem nº ${r.n} <span class="dica">${pos+1} de ${lista.length} neste filtro</span></h2>`;
  h += `<div class="status">${feito(r) ? '<span class="est ok">✓ Revisada</span>' : `<span class="est no">Faltam ${falta} de ${qs.length} perguntas</span>`}</div>`;
  const ms = motivos(r), duv = ms.filter(m => m.endsWith('_incerto')).map(m => (CAMPOS_TODOS.find(c => c.id === m.slice(0,-8)) || {curto:m}).curto.toLowerCase());
  if (ms.includes('auditoria')) h += `<span class="motivo aud"><b>${MOTIVO.auditoria[0]}.</b> ${MOTIVO.auditoria[1]}</span>`;
  if (duv.length) h += `<span class="motivo"><b>Modelo em dúvida:</b> ${duv.join(', ')}.</span>`;
  if (ms.includes('nao_confiavel')) h += `<span class="motivo"><b>${MOTIVO.nao_confiavel[0]}.</b> ${MOTIVO.nao_confiavel[1]}</span>`;
  h += `<div class="orig">Etapa 5: <b>${lbl(r.ambiente)}</b>, <b>${r.fogo==='sim'?'com fogo':'sem fogo'}</b></div>`;
  return h;
}
function barra(v, corte){ const p = x => (100*Math.min(Math.max(x,0),1)).toFixed(1)+'%';
  return `<div class="barra"><i style="width:${p(v)}"></i>${corte!=null?`<span class="corte" style="left:${p(corte)}"></span>`:''}</div>`; }
function secModelo(r){
  if (oculta(r)) return `<h2>Sugestão do modelo</h2><div class="oculto">Oculta na auditoria cega. Aparece depois que você marcar os campos.</div>`;
  const x = reg(r);
  let h = '';
  if (cego(r)){
    const c = x.cego || {};
    h += `<h2>Auditoria: você × modelo</h2><div class="comp"><span></span><span class="cab">Sua 1ª resposta</span><span class="cab">Modelo</span><span></span>` +
      CAMPOS.filter(k => aplica(r,k)).map(k => { const m = c[k.id], s = r.sug[k.id], ag = x[k.id], ok = m === s;
        return `<span class="nota" style="margin:0">${k.nome}</span><span>${ICON[m]||''} ${lbl(m)}${ag && ag!==m ? ` <span class="nota">(depois: ${lbl(ag)})</span>`:''}</span><span>${ICON[s]||''} ${lbl(s)}</span><span class="${ok?'ok':'no'}">${ok?'✓':'✗'}</span>`; }).join('') +
      `</div><div class="nota">O acerto do modelo usa só a 1ª resposta.</div>`;
  } else {
    if (!verPalpite) return `<button class="btn-palpite" id="btn-palpite" title="Tecla M">Mostrar o palpite do modelo (M)</button><div class="nota">Fica escondido para não influenciar: decida olhando a imagem; o palpite serve só para conferir.</div>`;
    h += `<h2>Palpite do modelo <span class="dica"><a href="#" id="btn-palpite">esconder (M)</a></span></h2>`;
  }
  h += CAMPOS.filter(k => aplica(r,k)).map(k => { const m = r.mod[k.id] || {};
    return `<div class="medida"><span class="nome">${k.curto}</span>${barra(+m.conf||0, LIM.conf_min)}<span class="val">${ICON[m.top1]||''} <b>${lbl(m.top1)}</b> ${(+m.conf||0).toFixed(2)}</span></div>
      <div class="nota">2ª opção: ${lbl(m.seg)}, margem ${(+m.margem||0).toFixed(2)}${r.sug[k.id]==='incerto' ? ' · abaixo do limite, por isso sugere <b>Incerto</b>' : ''}</div>`; }).join('');
  return h;
}
function opcoes(r,c){
  const atual = reg(r)[c.id] || '', sug = palpiteVisivel(r) ? r.sug[c.id] : null;
  const comFoto = c.op.filter(([v]) => v !== 'incerto'), inc = c.op.find(([v]) => v === 'incerto');
  const tiles = comFoto.map(([v,k]) => { const fs = (EXEMPLOS[c.id]||{})[v] || [];
    const fotos = fs.length ? `<div class="fotos">${fs.map(u => `<img src="${u}" alt="exemplo de ${lbl(v)}" loading="lazy">`).join('')}</div>` : `<div class="semfoto">${ICON[v]||''}</div>`;
    const ver = fs.length ? `<a class="ver" href="${fs[0]}" target="_blank" rel="noopener" title="Abrir o exemplo em tamanho grande">ampliar</a>` : '';
    return `<div class="tile ${atual===v?'on':''} ${sug===v?'sug':''}" role="button" tabindex="0" data-c="${c.id}" data-v="${v}" title="${esc(DEF[c.id][v]||'')}">${fotos}${ver}${sug===v?'<span class="palpite">palpite</span>':''}<div class="rot"><span>${lbl(v)}</span><kbd>${k.toUpperCase()}</kbd></div></div>`; }).join('');
  const incerto = inc ? `<div class="incerto-linha"><span class="opt ${atual==='incerto'?'on':''} ${sug==='incerto'?'sug':''}" role="button" tabindex="0" data-c="${c.id}" data-v="incerto" title="${esc(DEF[c.id].incerto||'')}">❔ Não dá para dizer <kbd>${inc[1].toUpperCase()}</kbd></span><span>use quando a imagem não permite decidir</span></div>` : '';
  return `<div class="tiles" style="--n:${comFoto.length}">${tiles}</div>${incerto}`;
}
function secCampo(r,c,i){
  if (!aplica(r,c)) return '';
  if (c.tipo === 'chips'){
    const x = reg(r), v = x[c.id] || '', sug = palpiteVisivel(r) ? r.sug[c.id] : null;
    const chips = c.op.map(([o,k]) => `<span class="opt ${v===o?'on':''} ${sug===o?'sug':''}" role="button" tabindex="0" data-c="${c.id}" data-v="${o}" title="${esc(DEF[c.id][o]||'')}${sug===o?' (palpite do modelo)':''}"><span class="ic">${ICON[o]||''}</span>${lbl(o)} <kbd>${k.toUpperCase()}</kbd></span>`).join('');
    return `<div class="sec curta ${perguntasDe(r)[ativa]===c?'ativa':''}" data-q="${c.id}"><h2><span class="n ${v?'ok':''}">${i}</span>${c.pergunta}</h2><div class="opcoes">${chips}</div><div class="def">${v ? `<b>${lbl(v)}:</b> ${esc(DEF[c.id][v]||'')}` : ''}</div></div>`;
  }
  if (!aplica(r,c)) return '';
  const x = reg(r), v = x[c.id] || '';
  const def = v ? `<b>${lbl(v)}:</b> ${esc(DEF[c.id][v]||'')}` : '';
  const dl = `<details class="criterios"><summary>Ver a definição de cada opção</summary><dl>${c.op.map(([o])=>`<dt>${lbl(o)}</dt><dd>${esc(DEF[c.id][o])}</dd>`).join('')}</dl></details>`;
  return `<div class="sec ${perguntasDe(r)[ativa]===c?'ativa':''}" data-q="${c.id}"><h2><span class="n ${x[c.id]?'ok':''}">${i}</span>${c.nome}</h2><div class="pergunta">${c.pergunta}</div><p class="crit">${c.crit}</p>${opcoes(r,c)}<div class="def">${def}</div>${dl}</div>`;
}
function ficha(r){
  const oc = oculta(r), m = r.med || {};
  const cores = [1,2,3].filter(i => m['cor'+i]).map(i => `<i class="sw" style="background:${m['cor'+i]}" title="${m['cor'+i]} · ${m['pct_cor'+i]}%"></i>`).join('');
  return [`<span>Tamanho <b>${m.largura ? m.largura+' × '+m.altura+' px' : '—'}</b>${m.orientacao ? ' ('+esc(m.orientacao)+')' : ''}</span>`,
    m.brilho !== undefined ? `<span>Iluminação <b>${esc(m.iluminacao||'—')}</b> (brilho ${m.brilho})</span>` : '',
    m.nitidez !== undefined ? `<span>Nitidez <b>${m.nitidez}</b> (${esc(m.faixa_nitidez)})</span>` : '',
    cores ? `<span class="cores">Cores ${cores}</span>` : '',
    m.pct_tons_fogo !== undefined ? `<span>Tons de fogo <b>${m.pct_tons_fogo}%</b></span>` : '',
    m.formato ? `<span>${esc(m.formato)}${m.jpeg_qualidade_est ? ' qualidade <b>'+m.jpeg_qualidade_est+'</b>' : ''}</span>` : '',
    m.camera_exif ? `<span>Câmera <b>${esc(m.camera_exif)}</b></span>` : '',
    m.pct_ceu_est !== undefined ? `<span>Céu ~<b>${m.pct_ceu_est}%</b> da metade de cima</span>` : '',
    m.pct_maior_foco !== undefined && r.fogo === 'sim' ? `<span>Maior foco <b>${m.pct_maior_foco}%</b> da imagem</span>` : '',
    m.moldura && m.moldura !== 'nenhuma' ? `<span><b>${esc(m.moldura.replace('_',' '))}</b> (${m.pct_borda}%)</span>` : '',
    m.blocos_visiveis === 'sim' ? `<span><b>blocos JPEG visíveis</b></span>` : '',
    m.ruido !== undefined ? `<span>Ruído <b>${m.ruido}</b></span>` : '',
    m.preto_e_branco === 'sim' ? `<span><b>preto e branco</b></span>` : '',
    `<span>Divisão <b>${lbl(r.split)}</b></span>`,
    `<span><a href="#" id="b-lente">🔍 Lupa (O)</a> · <a href="#" id="b-cheia">⛶ Tela cheia (P)</a></span>`,
    oc ? `<span class="cam" style="color:var(--mudo)">Caminho oculto na auditoria cega</span>` : `<span class="cam"><span>${esc(r.caminho)}</span><a href="${r.url}" target="_blank" rel="noopener">Abrir em nova aba</a></span>`].join('');
}
function mostrar(){
  montarFiltro();
  const total = DATA.length, n = nRevisadas(), aud = DATA.filter(cego);
  $('nrev').textContent = n; $('ntot').textContent = total; $('naud').textContent = aud.filter(r => reg(r).cego).length; $('ntaud').textContent = aud.length;
  $('t1').style.width = (100*n/total)+'%'; marcarPendencias();
  const r = lista[pos];
  if (!r){ $('s-situacao').innerHTML='<h2>Nenhuma imagem neste filtro</h2>'; $('s-modelo').innerHTML=''; $('campos').innerHTML=''; $('mapa').innerHTML=''; $('ficha').innerHTML=''; return; }
  const oc = oculta(r), img = $('foto');
  if (img.dataset.src !== r.url){ img.dataset.src = r.url; img.src = r.url; $('palco').className = 'palco'; mostradaEm = Date.now(); relogio(r); proximaAtiva(r); }
  else if (feito(r)) $('relogio').className = 'relogio pronto';
  img.onerror = () => { $('ficha').insertAdjacentHTML('afterbegin', '<span class="alerta-f">Não consegui abrir a imagem. O dataset continua no caminho do origem.json?</span>'); };
  $('selo').textContent = oc ? `nº ${r.n} · auditoria cega` : `nº ${r.n}`; $('selo').className = 'selo' + (cego(r) ? ' cego' : '');
  $('ficha').innerHTML = ficha(r);
  $('s-situacao').innerHTML = secSituacao(r); $('s-modelo').innerHTML = secModelo(r);
  const qs = perguntasDe(r); if (ativa >= qs.length) ativa = 0;
  let htmlc = '', g = '';
  qs.forEach((c,i) => { if (c.grupo !== g){ g = c.grupo; htmlc += `<div class="grupo-t">${g==='cena'?'A cena':'O fogo'}</div>`; } htmlc += secCampo(r,c,i+1); });
  if (r.fogo !== 'sim') htmlc += `<div class="grupo-t">O fogo</div><p class="crit">Imagem sem fogo: as perguntas sobre o fogo não se aplicam.</p>`;
  $('campos').innerHTML = htmlc;
  const at = document.querySelector('.sec.ativa'); if (at && mostrar.rolar){ at.scrollIntoView({block:'nearest'}); }
  document.querySelectorAll('.sec[data-q]').forEach(e => e.addEventListener('mousedown', () => { const i = perguntasDe(r).findIndex(c => c.id === e.dataset.q); if (i >= 0 && i !== ativa){ ativa = i; } }));
  const bp = $('btn-palpite'); if (bp) bp.onclick = ev => { ev.preventDefault(); alternarPalpite(); };
  const bl = $('b-lente'); if (bl) bl.onclick = ev => { ev.preventDefault(); alternarLente(); };
  const bc = $('b-cheia'); if (bc) bc.onclick = ev => { ev.preventDefault(); telaCheia(); };
  document.querySelectorAll('.tile .ver').forEach(a => a.onclick = ev => ev.stopPropagation());
  document.querySelectorAll('.opt, .tile').forEach(e => { e.onclick = () => marcar(e.dataset.c, e.dataset.v);
    e.onkeydown = ev => { if (ev.key===' ') { ev.preventDefault(); marcar(e.dataset.c, e.dataset.v); } }; });
  $('obs').value = reg(r).obs || ''; $('ace').disabled = oc || !verPalpite;
  $('mapa').innerHTML = lista.map((q,i) => `<i data-i="${i}" class="${feito(q)?'ok':''} ${cego(q)?'aud':''} ${i===pos?'cur':''}" title="nº ${q.n}"></i>`).join('');
  document.querySelectorAll('.mapa i').forEach(e => e.onclick = () => { pos = +e.dataset.i; mostrar(); });
}
function anotarObs(){ const r = lista[pos]; if (!r) return; reg(r).obs = $('obs').value; alteracoes++; salvar(); marcarPendencias(); }
function relogio(r){
  const el = $('relogio'), t = $('relogio-t');
  clearTimeout(relogio.t); el.className = 'relogio';
  if (feito(r)) { el.className = 'relogio pronto'; return; }
  void el.offsetWidth; el.className = 'relogio rodando'; t.textContent = 'Observe a imagem…';
  relogio.t = setTimeout(() => { t.textContent = 'Pode marcar'; el.className = 'relogio rodando pronto'; }, T_MIN);
}
function alternarPalpite(){
  verPalpite = !verPalpite; try { localStorage.setItem(KEY + '_palpite', verPalpite ? '1' : '0'); } catch(e) {}
  mostrar();
}
function marcarPendencias(){ $('alt').innerHTML = alteracoes ? `<span class="pend">${alteracoes}</span>` : ''; }
$('obs').oninput = anotarObs;
$('chips').innerHTML = OBS_RAPIDAS.map(t => `<span class="chip" role="button" tabindex="0">${esc(t)}</span>`).join('');
document.querySelectorAll('.chip').forEach(e => e.onclick = () => { const o = $('obs'), t = e.textContent;
  if (!o.value.includes(t)) { o.value = o.value ? o.value.replace(/[;\s]*$/,'') + '; ' + t : t; anotarObs(); } });
function marcar(c, v, teclado){
  const r = lista[pos]; if (!r) return;
  if (!aplica(r, CAMPOS.find(k => k.id===c))) return;
  const espera = T_MIN - (Date.now() - mostradaEm);
  if (!feito(r) && espera > 0){ toast(`Olhe a imagem com calma: dá para marcar em ${Math.ceil(espera/1000)} s`); return; }
  const antes = feito(r), x = reg(r);
  x[c] = (x[c] === v && !teclado) ? '' : v;   // clique repetido desmarca; tecla sempre marca
  if (!antes && feito(r)) x.seg = ((Date.now() - mostradaEm)/1000).toFixed(1);
  if (cego(r) && !x.cego && feito(r)){ x.cego = {quando:new Date().toISOString(), seg:x.seg}; obrig(r).forEach(k => x.cego[k] = x[k]); }
  if (x[c]) proximaAtiva(r);
  alteracoes++; salvar(); mostrar.rolar = true; mostrar(); mostrar.rolar = false;
  if (!antes && feito(r)){
    const n = nRevisadas();
    toast(n % 25 === 0 ? `${n} revisadas. Exporte o CSV para guardar o trabalho.` : (cego(r) ? 'Auditoria registrada. Veja a comparação com o modelo.' : 'Revisada'));
    if ($('auto').checked && !cego(r)) { const alvo = pos; setTimeout(() => { if (pos === alvo) ir(1); }, 350); }
  }
}
function aceitar(){
  const r = lista[pos]; if (!r || oculta(r)) return;
  if (!verPalpite){ toast('Mostre o palpite do modelo (M) antes de aceitá-lo'); return; }
  const espera = T_MIN - (Date.now() - mostradaEm);
  if (!feito(r) && espera > 0){ toast(`Olhe a imagem com calma: dá para aceitar em ${Math.ceil(espera/1000)} s`); return; }
  const x = reg(r), duvida = [], antes = feito(r);
  obrig(r).forEach(k => { const s = r.sug[k]; if (x[k]) return; if (s && s !== 'incerto') x[k] = s; else duvida.push(CAMPOS.find(c=>c.id===k).nome.toLowerCase()); });
  if (!antes && feito(r)) x.seg = ((Date.now() - mostradaEm)/1000).toFixed(1);
  alteracoes++; salvar();
  if (duvida.length){ mostrar(); toast('O modelo ficou em dúvida em ' + duvida.join(' e ') + ': marque você.'); return; }
  toast('Sugestão aceita nos campos vazios'); ir(1);
}
function limpar(){
  const r = lista[pos]; if (!r) return;
  const c = reg(r).cego; delete st[r.caminho]; if (c) reg(r).cego = c;
  alteracoes++; salvar(); toast(c ? 'Marcações apagadas. A 1ª resposta da auditoria foi mantida.' : 'Marcações apagadas'); mostrar();
}
function ir(d){ pos = Math.max(0, Math.min(lista.length-1, pos+d)); mostrar(); }
function proxNaoRevisada(){
  for (let k = 1; k <= lista.length; k++){ const i = (pos + k) % lista.length; if (!feito(lista[i])){ pos = i; mostrar(); return; } }
  toast('Todas as imagens deste filtro estão revisadas');
}
let lenteLigada = false;
function alternarLente(){ lenteLigada = !lenteLigada; if (!lenteLigada) $('lente').style.display = 'none'; toast(lenteLigada ? 'Lupa ligada: passe o mouse sobre a imagem (O desliga)' : 'Lupa desligada'); }
function telaCheia(){ const p = $('palco'); if (document.fullscreenElement) document.exitFullscreen(); else if (p.requestFullscreen) p.requestFullscreen(); }
$('foto').addEventListener('mousemove', ev => {
  const L = $('lente'); if (!lenteLigada || $('palco').className.includes('zoom')) { L.style.display = 'none'; return; }
  const img = $('foto'), b = img.getBoundingClientRect(), pb = $('palco').getBoundingClientRect(), Z = 3;
  const x = ev.clientX - b.left, y = ev.clientY - b.top;
  L.style.display = 'block'; L.style.backgroundImage = `url("${img.src}")`;
  L.style.backgroundSize = `${b.width * Z}px ${b.height * Z}px`;
  L.style.backgroundPosition = `${-(x * Z - 120)}px ${-(y * Z - 120)}px`;
  L.style.left = (ev.clientX - pb.left - 120 + $('palco').scrollLeft) + 'px'; L.style.top = (ev.clientY - pb.top - 120 + $('palco').scrollTop) + 'px';
});
$('foto').addEventListener('mouseleave', () => { $('lente').style.display = 'none'; });
function lupa(){ const m = $('palco'); m.className = m.className.includes('zoom') ? 'palco' : 'palco zoom'; }
function wilson(k, n){ const z = 1.96, p = k/n, d = 1 + z*z/n; const c = (p + z*z/(2*n))/d, m = z*Math.sqrt(p*(1-p)/n + z*z/(4*n*n))/d; return [Math.max(0,c-m), Math.min(1,c+m)]; }
function resumo(){
  const rev = DATA.filter(feito);
  const tab = c => { const a = {}; rev.forEach(r => { const v = reg(r)[c.id]; if (v) a[v] = (a[v]||0)+1; });
    return `<div><h4>${c.nome}</h4><table>${Object.entries(a).sort((p,q)=>q[1]-p[1]).map(([k,v])=>`<tr><td>${ICON[k]||''} ${lbl(k)}</td><td class="n">${v}</td></tr>`).join('') || '<tr><td>—</td></tr>'}</table></div>`; };
  const aud = DATA.filter(r => cego(r) && reg(r).cego);
  const prec = c => { const v = aud.filter(r => aplica(r,c)); const k = v.filter(r => reg(r).cego[c.id] === r.sug[c.id]).length, n = v.length;
    if (!n) return '<td class="n">—</td><td class="n">—</td>'; const w = wilson(k,n);
    return `<td class="n">${(100*k/n).toFixed(0)}% (${k}/${n})</td><td class="n">${(100*w[0]).toFixed(0)} a ${(100*w[1]).toFixed(0)}%</td>`; };
  $('cx').innerHTML = `<h3>Resumo</h3><p><b>${rev.length}</b> de ${DATA.length} revisadas. Auditoria cega: <b>${aud.length}</b> de ${DATA.filter(cego).length}.</p>
   <div class="colunas">${CAMPOS.map(tab).join('')}</div>
   <h4>Acerto do modelo na auditoria cega</h4><table><tr><th>Campo</th><th class="n">Acerto</th><th class="n">Intervalo de 95% (Wilson)</th></tr>
   ${CAMPOS.map(c => `<tr><td>${c.nome}</td>${prec(c)}</tr>`).join('')}</table>
   <p class="nota">Prévia. O número oficial sai do script 09d, a partir do CSV exportado.</p>
   <div style="display:flex;gap:8px;justify-content:space-between;margin-top:14px"><button id="zer">Apagar todas as marcações deste navegador</button><button id="fec" class="forte">Fechar</button></div>`;
  $('modal').className = 'on'; $('fec').focus(); $('fec').onclick = () => { $('modal').className = ''; };
  $('zer').onclick = () => { if (confirm('Apagar TODAS as marcações desta página salvas neste navegador? Exporte o CSV antes.') && confirm('Tem certeza? Isso não pode ser desfeito.')) { st = {}; salvar(); alteracoes = 0; $('modal').className=''; aplicar(); } };
}
function ajuda(){
  const linhas = [['1 a 6','Responde a pergunta destacada (a opção com aquele número); a próxima pergunta é destacada sozinha'],
    ['↑  ↓','Muda a pergunta destacada'],['←  →','Imagem anterior e próxima'],['N','Próxima imagem não revisada'],
    ['Enter','Aceitar o palpite nos campos vazios (só com o palpite à mostra; bloqueado na auditoria cega)'],['Backspace','Limpar as marcações desta imagem'],
    ['L','Ver em tamanho real'],['O','Lupa (acompanha o mouse)'],['P','Tela cheia'],['M','Mostrar ou esconder o palpite do modelo'],['?','Esta ajuda'],['Esc','Fechar']];
  $('cx').innerHTML = `<h3>Atalhos de teclado</h3><table>${linhas.map(([k,d])=>`<tr><td style="white-space:nowrap">${k.split('  ').map(t=>`<kbd>${t}</kbd>`).join(' ')}</td><td>${d}</td></tr>`).join('')}</table>
   <h4>Auditoria cega</h4><p style="font-size:13px;color:var(--mudo)">Nas imagens de auditoria, a sugestão e o caminho ficam ocultos. A primeira resposta completa é gravada como “cega” e é a única usada para medir o acerto do modelo.</p>
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
  const k = e.key.toLowerCase(), tratar = f => { e.preventDefault(); f(); };
  if (e.key==='ArrowRight') return tratar(() => ir(1));
  if (e.key==='ArrowLeft') return tratar(() => ir(-1));
  if (e.key==='Enter') return tratar(aceitar);
  if (e.key==='Backspace' || e.key==='Delete') return tratar(limpar);
  if (k==='n') return tratar(proxNaoRevisada);
  if (k==='l') return tratar(lupa);
  if (k==='m') return tratar(alternarPalpite);
  if (k==='o') return tratar(alternarLente);
  if (k==='p') return tratar(telaCheia);
  if (e.key==='?') return tratar(ajuda);
  const r0 = lista[pos];
  if (r0 && e.key==='ArrowDown') return tratar(() => { ativa = Math.min(perguntasDe(r0).length-1, ativa+1); mostrar.rolar = true; mostrar(); mostrar.rolar = false; });
  if (r0 && e.key==='ArrowUp') return tratar(() => { ativa = Math.max(0, ativa-1); mostrar.rolar = true; mostrar(); mostrar.rolar = false; });
  if (r0 && /^[1-9]$/.test(e.key)){ const c = perguntasDe(r0)[ativa]; const o = c && c.op[+e.key-1]; if (o) return tratar(() => marcar(c.id, o[0], true)); }
});
const csv = s => '"' + String(s ?? '').replace(/"/g,'""') + '"';
const COLS = ['n','caminho_original','motivos_revisao', ...ATRS.map(a => a+'_sugerido'), ...ATRS.map(a => a+'_confirmado'),
  'observacao','revisado', ...ATRS.map(a => a+'_cego'), 'quando_cego','segundos','segundos_cego'];
function exportar(){
  const linhas = DATA.map(r => { const x = reg(r), c = x.cego || {}, na = k => aplica(r, CAMPOS.find(q=>q.id===k)) ? '' : 'nao_se_aplica';
    return [r.n, r.caminho, r.motivos, ...ATRS.map(a => r.sug[a]), ...ATRS.map(a => x[a] || na(a)), x.obs||'', feito(r)?'sim':'nao',
      ...ATRS.map(a => c[a] || (c.quando ? na(a) : '')), c.quando||'', x.seg||'', c.seg||''].map(csv).join(','); });
  const blob = new Blob([COLS.join(',')+'\r\n'+linhas.join('\r\n')+'\r\n'], {type:'text/csv;charset=utf-8'});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = EXPORTAR_COMO;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  alteracoes = 0; mostrar(); toast(EXPORTAR_COMO + ' exportado. Guarde em relatorios/09_condicoes/');
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
  for (const l of t){ const g = n => (ix(n) >= 0 ? (l[ix(n)] || '') : ''); const k = g('caminho_original'); if (!k) continue;
    const limpa = v => v === 'nao_se_aplica' ? '' : v;
    const x = {obs:g('observacao')}; ATRS.forEach(a => { const v = limpa(g(a+'_confirmado')); if (v) x[a] = v; });
    if (g('segundos')) x.seg = g('segundos');
    if (g('quando_cego')){ x.cego = {quando:g('quando_cego'), seg:g('segundos_cego')}; ATRS.forEach(a => { const v = limpa(g(a+'_cego')); if (v) x.cego[a] = v; }); }
    if (ATRS.some(a => x[a]) || x.obs){ st[k] = {...(st[k]||{}), ...x}; c++; } }
  salvar(); aplicar(); toast(c + ' linhas importadas'); e.target.value = '';
};
$('dsnome').textContent = DATASET;
if (!DATA.some(cego)){ $('caud').hidden = true; document.querySelector('.legenda-mapa span:nth-child(3)').hidden = true; }
aplicar();
window.addEventListener('beforeunload', e => { if (alteracoes) { e.preventDefault(); e.returnValue = ''; } });
</script></body></html>
"""


def ler(caminho):
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--origem", default="relatorios/01_origem/origem.json")
    ap.add_argument("--revisao", default="relatorios/09_condicoes/revisao_condicoes.csv")
    ap.add_argument("--sugestoes", default="relatorios/09_condicoes/sugestoes_condicoes.csv")
    ap.add_argument("--medidas", default="relatorios/09_condicoes/medidas_auto.csv")
    ap.add_argument("--metadados", default="relatorios/09_condicoes/metadados_condicoes.json")
    ap.add_argument("--saida", help="padrão: o nome do --revisao com .html")
    a = ap.parse_args()
    base = Path(a.revisao).with_suffix("")
    a.saida = a.saida or str(base) + ".html"
    exportar_como = base.name + "_preenchida.csv"

    origem = json.loads(Path(a.origem).read_text(encoding="utf-8"))
    raiz = Path(origem["caminho_local"])
    lsug = ler(a.sugestoes)
    sug = {r["caminho_original"]: r for r in lsug}
    atrs = [at for at in ORDEM_ATR if f"{at}_sugerido" in lsug[0]]
    med = {r["caminho_original"]: r for r in ler(a.medidas)} if Path(a.medidas).exists() else {}
    lim = dict(LIM_PADRAO)
    if Path(a.metadados).exists():
        lim.update(json.loads(Path(a.metadados).read_text(encoding="utf-8")).get("limiares", {}))

    dados, faltam = [], []
    for r in ler(a.revisao):
        k = r["caminho_original"]
        s = sug.get(k)
        if s is None:
            faltam.append(k); continue
        m = med.get(k, {})
        dados.append({
            "n": int(r["n"]), "caminho": k, "motivos": r["motivos_revisao"],
            "url": (raiz / k.replace("\\", "/")).as_uri(), "split": s["split"], "ambiente": s["ambiente"], "fogo": s["fogo"],
            "sug": {at: s[f"{at}_sugerido"] for at in atrs},
            "mod": {at: {"top1": s.get(f"{at}_top1", ""), "conf": s.get(f"{at}_conf", ""), "seg": s.get(f"{at}_2a", ""),
                         "margem": s.get(f"{at}_margem", "")} for at in atrs},
            "med": {c: m[c] for c in ("largura", "altura", "brilho", "iluminacao", "nitidez", "faixa_brilho", "faixa_nitidez", "orientacao",
                                      "cor1", "pct_cor1", "cor2", "pct_cor2", "cor3", "pct_cor3", "pct_tons_fogo", "formato",
                                      "jpeg_qualidade_est", "camera_exif", "preto_e_branco", "pct_ceu_est", "pct_maior_foco", "moldura",
                                      "pct_borda", "blocos_visiveis", "ruido") if c in m}})
    if faltam:
        raise SystemExit(f"{len(faltam)} imagens da revisão sem sugestão em {a.sugestoes} (ex.: {faltam[0]}). Rode a 9b de novo.")

    # um exemplo nunca pode ser imagem da auditoria cega (mostraria a resposta); nas demais, é só referência
    na_lista = {d["caminho"].replace("\\", "/").split("/")[-1] for d in dados if d["motivos"] == "auditoria"}
    exemplos = {at: {op: [(raiz / "fire_dataset" / f).as_uri() for f in fs if (raiz / "fire_dataset" / f).exists() and f.split("/")[-1] not in na_lista]
                     for op, fs in ops.items()} for at, ops in EXEMPLOS.items()}

    def js(obj):
        return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")
    nome_ds = origem.get("dataset_ref", "") + (f" v{origem['versao_kaggle']}" if origem.get("versao_kaggle") else "")
    html = (HTML.replace("__DATA__", js(dados)).replace("__LIM__", js(lim)).replace("__DATASET__", js(nome_ds))
                .replace("__EXPORTAR_COMO__", js(exportar_como)).replace("__EXEMPLOS__", js(exemplos)).replace("__ATRS__", js(atrs)))
    Path(a.saida).write_text(html, encoding="utf-8")
    cegas = sum(d["motivos"] == "auditoria" for d in dados)
    print(f"Página gerada: {a.saida}\nImagens: {len(dados)} (das quais {cegas} cegas, de auditoria)")
    print(f"Medidas automáticas: {'sim' if med else 'não encontradas (rode a 9a para ver brilho e nitidez)'}")
    print(f"O botão Exportar baixa: {exportar_como}. Abra o arquivo no Chrome ou Edge (duplo clique).")


if __name__ == "__main__":
    main()
