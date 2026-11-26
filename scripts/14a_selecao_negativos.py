#!/usr/bin/env python3
"""
Etapa 14a - SELEÇÃO DOS NEGATIVOS DIFÍCEIS (SOMENTE LEITURA: nada é copiado, movido ou rotulado).

Pergunta (avaliação de 24/11/2026): quantos alarmes falsos as redes dão em cenas SEM fogo que parecem fogo ou
fumaça? Pôr do sol, neblina, nuvens, outono, luzes à noite e reflexos de sol. Um alarme falso a cada fim de tarde
inviabiliza o uso real, então a taxa de falso alarme é medida SÓ nessas cenas.

Este script monta um conjunto EXTERNO, só para avaliação (nunca para treino):
  * imagens da segunda fonte que NÃO entraram no dataset, na revisão da opção A nem no teste de atalho (13a);
  * nenhuma é quase igual (dHash <= --dist-min) a qualquer imagem de treino, validação ou teste;
  * o CLIP (o mesmo modelo da Etapa 5a) dá a cada imagem uma nota por tipo de cena difícil, contra frases de
    fogo, fumaça e cena comum; cada imagem vai para o tipo de maior nota;
  * em cada tipo, entre as --pool de maior nota, ficam as --por-tipo mais diferentes entre si (k-centros da 10c).
O CLIP só ESCOLHE candidatas. Quem decide o tipo da cena e se há fogo é a revisão humana, às cegas: a página não
mostra o tipo sugerido, a nota nem a pasta. Lareira, vela e churrasco não entram aqui: pelo critério do projeto,
chama visível é fogo. Eles e os faróis estão na 2ª rodada (Etapa 14c).

Entradas: relatorios/10_nova_fonte/<nome>/sugestoes.csv, selecao_A/revisao.csv, relatorios/13_atalho/revisao.csv
          e reserva.csv, data/treino_ignis/split_manifest.csv
Saídas  : relatorios/14_negativos/ (candidatos.csv com as notas, origem.json, resumo.txt) e a página
          revisao_negativos.html (o botão Exportar baixa revisao_negativos_preenchida.csv)

Uso:
  python scripts/14a_selecao_negativos.py --nova "C:\\Users\\maria\\.cache\\kagglehub\\datasets\\cristiancristancho\\forest-fire-image-dataset\\versions\\2"
         [--por-tipo 40] [--pool 120] [--dist-min 10] [--semente 42]
"""
import argparse, csv, json, os, random, re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath

import numpy as np
from PIL import Image

RAIZ = Path(__file__).resolve().parent.parent
NOME = "cristiancristancho_forest-fire-image-dataset"

# frases em inglês, como na Etapa 5a; a média das frases de cada tipo vira o "texto" do tipo
TIPOS = {
    "por_do_sol": ["a photo of a sunset", "a photo of a sunrise with an orange sky", "the sun setting behind trees",
                   "a red evening sky over a forest"],
    "neblina": ["a photo of fog in a forest", "a misty landscape", "morning mist over trees", "haze over the hills"],
    "nuvens": ["a photo of clouds in the sky", "low clouds over mountains", "dark storm clouds", "white clouds above a forest"],
    "outono": ["a photo of autumn foliage", "orange and red autumn leaves", "a forest in fall colors", "yellow autumn trees"],
    "luzes_noite": ["city lights at night", "street lights at night", "car headlights at night", "orange lights in the dark"],
    "reflexo_brilho": ["sunlight reflecting on water", "bright sun glare", "lens flare from the sun", "the sun shining through trees"],
}
CONTRASTE = {
    "fogo": ["a photo of a forest fire", "a photo of flames", "a burning building"],
    "fumaca": ["a photo of smoke from a fire", "a column of smoke rising"],
    "comum": ["an ordinary photo of a forest on a clear day", "a photo of a street during the day", "a photo of a house"],
}
NOME_TIPO = {"por_do_sol": "Pôr ou nascer do sol", "neblina": "Neblina ou névoa", "nuvens": "Nuvens",
             "outono": "Folhagem de outono", "luzes_noite": "Luzes à noite", "reflexo_brilho": "Reflexo ou brilho de sol"}


def ler(c):
    with open(c, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def gravar(c, linhas, cols):
    with open(c, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(linhas)


def abrir(nova, rel):
    return Image.open(nova / Path(*rel.replace("\\", "/").split("/")))


def dhash(img):   # o mesmo da Etapa 11 (o manifesto do treino foi gravado com ele)
    g = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    px = g.tobytes(); bits = 0
    for lin in range(8):
        for col in range(8):
            bits = (bits << 1) | (px[lin * 9 + col] > px[lin * 9 + col + 1])
    return bits


def descritor(rgb):   # o mesmo da Etapa 10c
    g = np.asarray(rgb.convert("L").resize((16, 16), Image.Resampling.BILINEAR), dtype=np.float32).ravel() / 255
    p = np.asarray(rgb.resize((32, 32), Image.Resampling.BILINEAR), dtype=np.uint8).reshape(-1, 3) // 64
    h = np.bincount(p[:, 0] * 16 + p[:, 1] * 4 + p[:, 2], minlength=64).astype(np.float32); h /= h.sum()
    return np.concatenate([g / np.sqrt(len(g)), np.sqrt(h)])


def k_centros(X, k):
    k = min(k, len(X)); esc = [0]; dmin = np.linalg.norm(X - X[0], axis=1)
    while len(esc) < k:
        i = int(np.argmax(dmin)); esc.append(i); dmin = np.minimum(dmin, np.linalg.norm(X - X[i], axis=1))
    return esc


def notas_clip(nova, caminhos, nome_modelo, lote=16):
    """Probabilidade (softmax) de cada tipo difícil e de cada contraste, por imagem."""
    import torch
    from transformers import CLIPModel, CLIPProcessor
    disp = "cuda" if torch.cuda.is_available() else "cpu"
    modelo = CLIPModel.from_pretrained(nome_modelo).to(disp).eval()
    proc = CLIPProcessor.from_pretrained(nome_modelo)
    escala = modelo.logit_scale.exp().item()
    rotulos = list(TIPOS) + list(CONTRASTE)
    frases = list(TIPOS.values()) + list(CONTRASTE.values())

    def emb_texto(fr):
        with torch.no_grad():
            t = proc(text=fr, return_tensors="pt", padding=True).to(disp)
            e = modelo.text_projection(modelo.text_model(input_ids=t["input_ids"], attention_mask=t["attention_mask"]).pooler_output)
            e = e / e.norm(dim=-1, keepdim=True)
        m = e.mean(dim=0); return m / m.norm()

    E = torch.stack([emb_texto(f) for f in frases])
    saidas = []
    for k in range(0, len(caminhos), lote):
        imgs = []
        for c in caminhos[k:k + lote]:          # abre aos poucos: milhares de imagens não cabem na memória
            with abrir(nova, c) as im: imgs.append(im.convert("RGB").copy())
        with torch.no_grad():
            x = proc(images=imgs, return_tensors="pt").to(disp)
            e = modelo.visual_projection(modelo.vision_model(pixel_values=x["pixel_values"]).pooler_output)
            e = e / e.norm(dim=-1, keepdim=True)
            p = (escala * e @ E.T).softmax(dim=-1).cpu().numpy()
        saidas += [dict(zip(rotulos, linha.tolist())) for linha in p]
        print(f"  CLIP {min(k + lote, len(caminhos))}/{len(caminhos)}", end="\r")
    print()
    return saidas


def notas_falsas(caminhos, semente):
    """SÓ PARA TESTAR O PIPELINE (sem modelo): notas aleatórias e determinísticas."""
    rng = np.random.default_rng(semente); rot = list(TIPOS) + list(CONTRASTE)
    return [dict(zip(rot, (lambda v: (v / v.sum()).tolist())(rng.random(len(rot)) ** 4))) for _ in caminhos]


PAGINA = r"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Negativos difíceis – Ignis Alert</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{--papel:#f3f4f1;--folha:#fff;--tinta:#1e2421;--mudo:#5f6862;--linha:#d5d9d3;--brasa:#b93d0f;--mata:#2d6a4a;--palco:#1a1d1b}
@media (prefers-color-scheme:dark){:root{--papel:#151816;--folha:#1d211f;--tinta:#e9ece8;--mudo:#9aa39d;--linha:#343a36;--mata:#6cc596;--palco:#0e100f}}
*{box-sizing:border-box}body{margin:0;height:100dvh;display:flex;flex-direction:column;background:var(--papel);color:var(--tinta);font:14px/1.45 "Segoe UI",system-ui,sans-serif}
header{display:flex;gap:14px;align-items:center;padding:8px 16px;background:var(--folha);border-bottom:1px solid var(--linha);flex-wrap:wrap}
header h1{font-size:15px;margin:0}.barra{flex:1;min-width:160px;height:6px;background:var(--linha);border-radius:3px;overflow:hidden}.barra i{display:block;height:100%;background:var(--mata)}
button{font:inherit;padding:6px 12px;border:1px solid var(--linha);border-radius:6px;background:var(--folha);color:var(--tinta);cursor:pointer}
button.pri{background:var(--brasa);border-color:var(--brasa);color:#fff;font-weight:600}
main{flex:1;display:grid;grid-template-columns:1fr 420px;min-height:0}
.palco{background:var(--palco);display:flex;align-items:center;justify-content:center;min-height:0;padding:12px}
.palco img{max-width:100%;max-height:100%;object-fit:contain}.erro{color:#fff;padding:20px}
aside{overflow:auto;padding:14px 16px;background:var(--folha);border-left:1px solid var(--linha)}
h2{font-size:16px;margin:0 0 8px}fieldset{border:0;border-top:1px solid var(--linha);padding:10px 0 6px;margin:0}legend{font-weight:600;padding:0}
.crit{color:var(--mudo);font-size:12px;margin:2px 0 6px}.ops{display:flex;flex-wrap:wrap;gap:6px}
.ops button{padding:5px 10px}.ops button.on{background:var(--mata);border-color:var(--mata);color:#fff}
.ops kbd{font-size:10px;opacity:.7;margin-left:4px}
textarea{width:100%;min-height:44px;font:inherit;padding:6px;border:1px solid var(--linha);border-radius:6px;background:var(--papel);color:var(--tinta)}
.nav{display:flex;gap:8px;margin-top:12px}.nav button{flex:1}.mapa{display:flex;flex-wrap:wrap;gap:3px;margin-top:12px}
.mapa span{width:12px;height:12px;border-radius:2px;background:var(--linha);cursor:pointer}.mapa span.ok{background:var(--mata)}.mapa span.at{outline:2px solid var(--brasa)}
.dica{color:var(--mudo);font-size:12px;margin-top:10px}
@media (max-width:900px){main{grid-template-columns:1fr}.palco{height:50vh}}
</style></head><body>
<header><h1>Negativos difíceis · revisão cega</h1><div class="barra"><i id="prog"></i></div><span id="cont"></span>
<button id="exp" class="pri">Exportar CSV</button></header>
<main><div class="palco"><img id="img" alt="Imagem em revisão"></div>
<aside><h2 id="tit"></h2><div id="campos"></div>
<fieldset><legend>Observação</legend><textarea id="obs" placeholder="Opcional"></textarea></fieldset>
<div class="nav"><button id="ant">← Anterior</button><button id="prox">Próxima →</button></div>
<div class="mapa" id="mapa"></div>
<p class="dica">Teclas: 1 a 7 escolhem a cena, F/N/I o fogo, S/M/D a fumaça (sim, não, dúvida); ← → navegam.
Ao completar os três campos, a página passa para a próxima. Tudo fica salvo no navegador até você exportar.</p></aside></main>
<script>
const DATA = __DATA__, CHAVE = __CHAVE__;
const CAMPOS = {
  cena: {t:'Cena', crit:'O que mais pode ser confundido com fogo ou fumaça nesta foto. Se nada parece fogo nem fumaça, "nenhuma".',
         ops:[['por_do_sol','Pôr ou nascer do sol','1'],['neblina','Neblina ou névoa','2'],['nuvens','Nuvens','3'],['outono','Folhagem de outono','4'],
              ['luzes_noite','Luzes à noite','5'],['reflexo_brilho','Reflexo ou brilho de sol','6'],['nenhuma','Nenhuma: cena comum','7']]},
  fogo: {t:'Fogo', crit:'Sim só com chama visível, mesmo pequena (lareira e vela também contam). Céu laranja, brilho ou só fumaça: não.',
         ops:[['sim','Sim','F'],['nao','Não','N'],['incerto','Incerto','I']]},
  fumaca: {t:'Fumaça', crit:'Fumaça de queima visível. Neblina e nuvem não contam; na dúvida, incerto.',
         ops:[['sim','Sim','S'],['nao','Não','M'],['incerto','Incerto','D']]},
};
let est = {}; try { est = JSON.parse(localStorage.getItem(CHAVE) || '{}'); } catch (e) {}
const salvar = () => { try { localStorage.setItem(CHAVE, JSON.stringify(est)); } catch (e) {} };
let i = 0;
const reg = r => est[r.n] || (est[r.n] = {});
const feito = r => Object.keys(CAMPOS).every(c => reg(r)[c]);
function mostrar() {
  const r = DATA[i], x = reg(r);
  let im = document.getElementById('img');
  if (im.tagName !== 'IMG') { const n = document.createElement('img'); n.id = 'img'; im.replaceWith(n); im = n; }
  im.onerror = () => im.replaceWith(Object.assign(document.createElement('div'), {className:'erro', id:'img', textContent:'Não consegui abrir a imagem nº ' + r.n}));
  im.src = r.url;
  document.getElementById('tit').textContent = `Imagem nº ${r.n} · ${i + 1} de ${DATA.length}`;
  document.getElementById('campos').innerHTML = Object.entries(CAMPOS).map(([c, d]) => `<fieldset><legend>${d.t}</legend><div class="crit">${d.crit}</div>
    <div class="ops">${d.ops.map(([v, t, k]) => `<button data-c="${c}" data-v="${v}" class="${x[c] === v ? 'on' : ''}">${t}<kbd>${k}</kbd></button>`).join('')}</div></fieldset>`).join('');
  document.getElementById('obs').value = x.obs || '';
  const n = DATA.filter(feito).length;
  document.getElementById('cont').textContent = `${n} de ${DATA.length}`;
  document.getElementById('prog').style.width = (100 * n / DATA.length) + '%';
  document.getElementById('mapa').innerHTML = DATA.map((d, k) => `<span title="nº ${d.n}" data-k="${k}" class="${feito(d) ? 'ok' : ''} ${k === i ? 'at' : ''}"></span>`).join('');
}
function marcar(c, v) {
  const r = DATA[i], x = reg(r), novo = !feito(r);
  x[c] = v; if (!x.quando) x.quando = new Date().toISOString(); salvar();
  if (novo && feito(r) && i < DATA.length - 1) i++;
  mostrar();
}
document.getElementById('campos').onclick = e => { const b = e.target.closest('button'); if (b) marcar(b.dataset.c, b.dataset.v); };
document.getElementById('obs').oninput = e => { reg(DATA[i]).obs = e.target.value; salvar(); };
document.getElementById('mapa').onclick = e => { if (e.target.dataset.k) { i = +e.target.dataset.k; mostrar(); } };
document.getElementById('ant').onclick = () => { i = Math.max(0, i - 1); mostrar(); };
document.getElementById('prox').onclick = () => { i = Math.min(DATA.length - 1, i + 1); mostrar(); };
const TECLA = {};
for (const [c, d] of Object.entries(CAMPOS)) for (const [v, , k] of d.ops) TECLA[k.toLowerCase()] = [c, v];
document.onkeydown = e => {
  if (e.target.tagName === 'TEXTAREA') return;
  if (e.key === 'ArrowLeft') return document.getElementById('ant').click();
  if (e.key === 'ArrowRight') return document.getElementById('prox').click();
  const t = TECLA[e.key.toLowerCase()]; if (t) marcar(t[0], t[1]);
};
const q = s => '"' + String(s ?? '').replace(/"/g, '""') + '"';
document.getElementById('exp').onclick = () => {
  const cols = ['n','caminho_relativo','cena','fogo','fumaca','observacao','quando','revisado'];
  const lin = DATA.map(r => { const x = reg(r); return [r.n, r.caminho, x.cena, x.fogo, x.fumaca, x.obs, x.quando, feito(r) ? 'sim' : 'nao'].map(q).join(','); });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([cols.join(',') + '\r\n' + lin.join('\r\n') + '\r\n'], {type:'text/csv;charset=utf-8'}));
  a.download = 'revisao_negativos_preenchida.csv'; document.body.appendChild(a); a.click(); a.remove();
};
mostrar();
</script></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nova", required=True)
    ap.add_argument("--por-tipo", type=int, default=40)
    ap.add_argument("--pool", type=int, default=120, help="em cada tipo, quantas de maior nota entram na seleção de diversidade")
    ap.add_argument("--dist-min", type=int, default=10)
    ap.add_argument("--semente", type=int, default=42)
    ap.add_argument("--modelo", default="openai/clip-vit-base-patch16")
    ap.add_argument("--manifesto", default="data/treino_ignis/split_manifest.csv")
    ap.add_argument("--saida", default="relatorios/14_negativos")
    ap.add_argument("--raiz-registrada", default=None, help="caminho a gravar no origem.json (ao rodar fora do Windows)")
    ap.add_argument("--teste-sem-modelo", action="store_true", help="notas aleatórias, só para testar o script")
    a = ap.parse_args()

    nova = Path(a.nova)
    if not nova.is_dir(): raise SystemExit(f"Pasta da nova fonte não existe: {nova}")
    p10 = RAIZ / "relatorios/10_nova_fonte" / NOME
    sug = ler(p10 / "sugestoes.csv")
    usadas = {r["caminho_relativo"] for r in ler(p10 / "selecao_A/revisao.csv")}
    usadas |= {r["caminho_relativo"] for r in ler(RAIZ / "relatorios/13_atalho/revisao.csv")}
    man = ler(RAIZ / a.manifesto)
    dh_ds = np.array([int(m["dhash"], 16) for m in man], dtype=np.uint64)
    sai = RAIZ / a.saida; sai.mkdir(parents=True, exist_ok=True)

    pool = sorted((r for r in sug if r["situacao"] == "candidata" and r["caminho_relativo"] not in usadas),
                  key=lambda r: r["caminho_relativo"])
    print(f"Candidatas fora do dataset, da opção A e do teste de atalho: {len(pool)}. Conferindo dHash...")
    ok, desc, prox = [], [], 0
    for k, r in enumerate(pool):
        with abrir(nova, r["caminho_relativo"]) as im:
            rgb = im.convert("RGB")
        d = int(min(bin(int(x)).count("1") for x in (dh_ds ^ np.uint64(dhash(rgb)))))
        if d <= a.dist_min: prox += 1; continue
        ok.append(r); desc.append(descritor(rgb))
        if k % 200 == 0: print(f"  dHash {k}/{len(pool)}", end="\r")
    print(f"\n  quase iguais ao dataset (dHash <= {a.dist_min}): {prox} | seguem: {len(ok)}")

    cams = [r["caminho_relativo"] for r in ok]
    notas = notas_falsas(cams, a.semente) if a.teste_sem_modelo else notas_clip(nova, cams, a.modelo)
    for r, s in zip(ok, notas):
        r["tipo_sugerido"] = max(TIPOS, key=lambda t: s[t])
        r["nota_tipo"] = s[r["tipo_sugerido"]]
        r["nota_fogo"], r["nota_fumaca"], r["nota_comum"] = s["fogo"], s["fumaca"], s["comum"]
    X = np.stack(desc); idx = {r["caminho_relativo"]: k for k, r in enumerate(ok)}

    escolhidas, resumo_tipo = [], []
    for t in TIPOS:
        grupo = sorted((r for r in ok if r["tipo_sugerido"] == t), key=lambda r: -r["nota_tipo"])[:a.pool]
        if not grupo: resumo_tipo.append((t, 0, 0)); continue
        esc = [grupo[i] for i in k_centros(X[[idx[r["caminho_relativo"]] for r in grupo]], a.por_tipo)]
        escolhidas += esc
        resumo_tipo.append((t, sum(r["tipo_sugerido"] == t for r in ok), len(esc)))

    random.Random(a.semente).shuffle(escolhidas)       # a ordem não revela o tipo sugerido
    for n, r in enumerate(escolhidas, 1): r["n"] = n
    gravar(sai / "candidatos.csv", escolhidas,
           ["n", "caminho_relativo", "pasta", "tipo_sugerido", "nota_tipo", "nota_fogo", "nota_fumaca", "nota_comum",
            "fogo_sugerido", "largura", "altura", "sha256"])
    raiz_txt = a.raiz_registrada or str(nova.resolve())
    (sai / "origem.json").write_text(json.dumps({"dataset_ref": "cristiancristancho/forest-fire-image-dataset", "versao_kaggle": 2,
                                                 "caminho_local": raiz_txt}, ensure_ascii=False, indent=2), encoding="utf-8")
    raiz = (PureWindowsPath if os.name != "nt" and re.match(r"^[A-Za-z]:[\\/]", raiz_txt) else Path)(raiz_txt)
    dados = [{"n": r["n"], "caminho": r["caminho_relativo"], "url": (raiz / r["caminho_relativo"]).as_uri()} for r in escolhidas]
    html = (PAGINA.replace("__DATA__", json.dumps(dados, ensure_ascii=False).replace("</", "<\\/"))
                  .replace("__CHAVE__", json.dumps("ignis_negativos_" + str(a.semente))))
    (sai / "revisao_negativos.html").write_text(html, encoding="utf-8")

    txt = [f"Etapa 14a gerada em {datetime.now(timezone.utc).isoformat(timespec='seconds')} | SOMENTE LEITURA | semente {a.semente}",
           f"modelo: {'NOTAS FALSAS (teste do script)' if a.teste_sem_modelo else a.modelo}",
           f"candidatas fora do dataset, da opção A e do teste de atalho: {len(pool)} | quase iguais ao dataset: {prox} | avaliadas: {len(ok)}",
           "", f"  {'tipo sugerido pelo CLIP':<26} {'imagens com esse tipo':>22} {'escolhidas':>11}"]
    txt += [f"  {NOME_TIPO[t]:<26} {n:>22} {e:>11}" for t, n, e in resumo_tipo]
    txt += [f"  {'total':<26} {len(ok):>22} {len(escolhidas):>11}", "",
            "Revisão: abra relatorios/14_negativos/revisao_negativos.html, marque cena, fogo e fumaça de cada imagem e",
            "exporte revisao_negativos_preenchida.csv para relatorios/14_negativos/. Depois rode a Etapa 14b."]
    (sai / "resumo.txt").write_text("\n".join(txt) + "\n", encoding="utf-8")
    print("\n".join(txt))


if __name__ == "__main__":
    main()
