#!/usr/bin/env python3
"""
Etapa 16 - PRIVACIDADE E VERSÃO PÚBLICA DO DATASET (os originais e data/treino_ignis NÃO são alterados).

Pedido da avaliação de 24/11/2026: tirar os metadados (EXIF: GPS, aparelho, data) e borrar rostos e placas antes
de distribuir o dataset, e marcar uma versão.

Três passos:
  1) triagem    conta os metadados de cada imagem (quantas têm GPS, aparelho, data, orientação) e usa o CLIP para
                apontar as imagens que podem ter ROSTO ou PLACA de veículo. Gera a página marcar.html.
                O OpenCV 5 não traz mais os detectores Haar de rosto e placa; por isso a IA só ESCOLHE as candidatas
                e uma PESSOA desenha os retângulos a borrar (a mesma regra do projeto: a máquina sugere, a pessoa decide).
  2) marcar     abra relatorios\\16_privacidade\\marcar.html, arraste um retângulo sobre cada rosto ou placa
                legível, ou clique "Nada a borrar". Exporte marcacoes.csv para relatorios\\16_privacidade\\.
  3) exportar   monta data/publico/ignis_alert_<versao>/ com a mesma estrutura do treino:
                  * metadados removidos SEM recodificar (JPEG: tira APP1/EXIF-XMP, APP13/IPTC e comentários;
                    PNG: tira tEXt/iTXt/zTXt/eXIf/tIME). Os pixels ficam idênticos aos do treino;
                  * só as imagens com retângulo marcado são recodificadas (JPEG qualidade 95), com desfoque forte;
                  * split_manifest_publico.csv com o SHA-256 do treino e o da cópia pública, e o que mudou;
                  * confere no fim que nenhuma cópia tem EXIF, GPS ou texto embutido.

Uso:
  python scripts/16_privacidade.py triagem
  python scripts/16_privacidade.py exportar --marcacoes relatorios\\16_privacidade\\marcacoes.csv --versao v1.0
Depois: git tag -a v1.0 -m "..." && git push origin v1.0   (o manifesto público fica registrado em relatorios/16_privacidade/)
"""
import argparse, csv, hashlib, io, json, shutil, struct, sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

RAIZ = Path(__file__).resolve().parent.parent
SAI = RAIZ / "relatorios/16_privacidade"
FRASES = {
    "rosto": ["a close-up photo of a person's face", "a portrait of a person", "people standing and looking at the camera"],
    "placa": ["a car license plate", "the back of a car with its license plate", "a parked car seen up close", "a truck on a road"],
    "comum": ["a photo of a forest fire", "a landscape with trees", "a building on fire", "a photo of smoke in the sky"],
}
PNG_FORA = {b"tEXt", b"iTXt", b"zTXt", b"eXIf", b"tIME"}


def sha256(b): return hashlib.sha256(b).hexdigest()


def ler_manifesto(dados):
    arq = dados / "split_manifest.csv"
    if not arq.is_file(): sys.exit(f"[PARADO] Não achei {arq}. Rode antes a Etapa 11.")
    return list(csv.DictReader(arq.open(encoding="utf-8")))


# ------------------------------------------------------------------ metadados
def metadados(caminho):
    """o que a imagem carrega além dos pixels."""
    with Image.open(caminho) as im:
        ex = im.getexif(); info = dict(im.info)
        gps = bool(ex.get_ifd(0x8825)) if ex else False
        return {"formato": im.format, "exif": "sim" if len(ex) else "", "gps": "sim" if gps else "",
                "aparelho": " ".join(str(ex.get(t, "")) for t in (0x010F, 0x0110)).strip() if ex else "",
                "data": str(ex.get(0x0132, "")) if ex else "", "orientacao": str(ex.get(0x0112, "")) if ex else "",
                "xmp": "sim" if ("xmp" in info or "XML:com.adobe.xmp" in info) else "",
                "texto": "sim" if any(k in info for k in ("comment", "Comment", "Description", "Author", "parameters")) else ""}


def limpar_jpeg(b):
    if b[:2] != b"\xff\xd8": raise ValueError("não é JPEG")
    out, i = bytearray(b[:2]), 2
    while i < len(b):
        if b[i] != 0xFF: raise ValueError("marcador JPEG inválido")
        m = b[i + 1]
        if m == 0xDA:                                         # SOS: daqui em diante são os dados da imagem
            out += b[i:]; break
        if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7: out += b[i:i + 2]; i += 2; continue
        n = struct.unpack(">H", b[i + 2:i + 4])[0]
        if m not in (0xE1, 0xED, 0xFE): out += b[i:i + 2 + n]  # tira EXIF/XMP, IPTC e comentários; mantém ICC (APP2)
        i += 2 + n
    return bytes(out)


def limpar_png(b):
    if b[:8] != b"\x89PNG\r\n\x1a\n": raise ValueError("não é PNG")
    out, i = bytearray(b[:8]), 8
    while i < len(b):
        n = struct.unpack(">I", b[i:i + 4])[0]; tipo = b[i + 4:i + 8]
        if tipo not in PNG_FORA: out += b[i:i + 12 + n]
        i += 12 + n
    return bytes(out)


def sem_metadados(b):
    if b[:2] == b"\xff\xd8": return limpar_jpeg(b)
    if b[:8] == b"\x89PNG\r\n\x1a\n": return limpar_png(b)
    with Image.open(io.BytesIO(b)) as im:                    # outro formato: regrava só os pixels
        buf = io.BytesIO(); im.convert("RGB").save(buf, "JPEG", quality=95); return buf.getvalue()


# ------------------------------------------------------------------ 1) triagem
def notas_clip(caminhos, modelo, lote=16):
    import torch
    from transformers import CLIPModel, CLIPProcessor
    disp = "cuda" if torch.cuda.is_available() else "cpu"
    m = CLIPModel.from_pretrained(modelo).to(disp).eval(); proc = CLIPProcessor.from_pretrained(modelo)
    rot = list(FRASES)
    with torch.no_grad():
        E = []
        for fr in FRASES.values():
            t = proc(text=fr, return_tensors="pt", padding=True).to(disp)
            e = m.get_text_features(**t); e = e if torch.is_tensor(e) else e.pooler_output
            e = e / e.norm(dim=-1, keepdim=True); e = e.mean(0); E.append(e / e.norm())
        E = torch.stack(E); out = []
        for k in range(0, len(caminhos), lote):
            ims = []
            for c in caminhos[k:k + lote]:
                with Image.open(c) as im: ims.append(im.convert("RGB"))
            e = m.get_image_features(**proc(images=ims, return_tensors="pt").to(disp)); e = e if torch.is_tensor(e) else e.pooler_output
            e = e / e.norm(dim=-1, keepdim=True)
            p = (m.logit_scale.exp() * e @ E.T).softmax(-1).cpu().numpy()
            out += [dict(zip(rot, l.tolist())) for l in p]
            print(f"  CLIP {min(k + lote, len(caminhos))}/{len(caminhos)}", end="\r")
    print(); return out


PAGINA = r"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Rostos e placas – Ignis Alert</title>
<style>body{margin:0;font:14px system-ui;background:#f3f4f1;color:#1e2421;display:flex;flex-direction:column;height:100vh}
header{display:flex;gap:12px;align-items:center;padding:8px 14px;background:#fff;border-bottom:1px solid #d5d9d3}
header h1{font-size:15px;margin:0;flex:1}button{font:inherit;padding:6px 12px;border:1px solid #d5d9d3;border-radius:6px;background:#fff;cursor:pointer}
button.pri{background:#b93d0f;color:#fff;border-color:#b93d0f}main{flex:1;display:grid;grid-template-columns:1fr 300px;min-height:0}
#palco{position:relative;background:#1a1d1b;display:flex;align-items:center;justify-content:center;overflow:hidden}
canvas{max-width:100%;max-height:100%;cursor:crosshair}aside{padding:12px;background:#fff;overflow:auto}
.lst div{display:flex;justify-content:space-between;margin:4px 0}.ok{color:#2d6a4a;font-weight:600}</style></head><body>
<header><h1>Rostos e placas legíveis · arraste um retângulo sobre cada um</h1><span id="cont"></span><button class="pri" id="exp">Exportar CSV</button></header>
<main><div id="palco"><canvas id="c"></canvas></div><aside><b id="tit"></b><p>Borre só o que identifica alguém: rosto reconhecível ou placa
que dá para ler. Silhueta de longe e carro sem placa visível não precisam.</p>
<div class="lst" id="lst"></div><p><button id="nada">Nada a borrar (N)</button> <button id="desf">Desfazer último (Z)</button></p>
<p><button id="ant">← Anterior</button> <button id="prox">Próxima →</button></p><p id="st"></p></aside></main>
<script>
const DATA = __DATA__, CHAVE = 'ignis_privacidade_v1';
let est = {}; try { est = JSON.parse(localStorage.getItem(CHAVE) || '{}'); } catch (e) {}
const salvar = () => { try { localStorage.setItem(CHAVE, JSON.stringify(est)); } catch (e) {} };
let i = 0, img = new Image(), ini = null, atual = null; const c = document.getElementById('c'), g = c.getContext('2d');
const reg = d => est[d.path] || (est[d.path] = {caixas: [], feito: false});
function desenhar() { g.drawImage(img, 0, 0); g.lineWidth = Math.max(2, img.width / 300);
  for (const b of reg(DATA[i]).caixas.concat(atual ? [atual] : [])) { g.strokeStyle = '#ff3b1f'; g.fillStyle = 'rgba(255,59,31,.25)';
    g.fillRect(b[0], b[1], b[2] - b[0], b[3] - b[1]); g.strokeRect(b[0], b[1], b[2] - b[0], b[3] - b[1]); } }
function mostrar() { const d = DATA[i]; img = new Image(); img.onload = () => { c.width = img.width; c.height = img.height; desenhar(); }; img.src = d.url;
  const r = reg(d); document.getElementById('tit').textContent = `${i + 1} de ${DATA.length} · ${d.path}`;
  document.getElementById('lst').innerHTML = r.caixas.map((b, k) => `<div><span>retângulo ${k + 1}</span><span>${b[2] - b[0]}×${b[3] - b[1]} px</span></div>`).join('');
  document.getElementById('st').innerHTML = r.feito ? (r.caixas.length ? `<span class="ok">${r.caixas.length} a borrar</span>` : '<span class="ok">nada a borrar</span>') : 'não revisada';
  document.getElementById('cont').textContent = `${DATA.filter(x => reg(x).feito).length} de ${DATA.length} revisadas`; }
const pos = e => { const r = c.getBoundingClientRect(); return [Math.round((e.clientX - r.left) * c.width / r.width), Math.round((e.clientY - r.top) * c.height / r.height)]; };
c.onmousedown = e => { ini = pos(e); };
c.onmousemove = e => { if (!ini) return; const p = pos(e); atual = [Math.min(ini[0], p[0]), Math.min(ini[1], p[1]), Math.max(ini[0], p[0]), Math.max(ini[1], p[1])]; desenhar(); };
c.onmouseup = () => { if (atual && atual[2] - atual[0] > 3 && atual[3] - atual[1] > 3) { const r = reg(DATA[i]); r.caixas.push(atual); r.feito = true; salvar(); } ini = atual = null; mostrar(); };
document.getElementById('nada').onclick = () => { const r = reg(DATA[i]); r.caixas = []; r.feito = true; salvar(); if (i < DATA.length - 1) i++; mostrar(); };
document.getElementById('desf').onclick = () => { reg(DATA[i]).caixas.pop(); salvar(); mostrar(); };
document.getElementById('ant').onclick = () => { i = Math.max(0, i - 1); mostrar(); };
document.getElementById('prox').onclick = () => { i = Math.min(DATA.length - 1, i + 1); mostrar(); };
document.onkeydown = e => { const k = e.key.toLowerCase(); if (k === 'n') document.getElementById('nada').click(); if (k === 'z') document.getElementById('desf').click();
  if (e.key === 'ArrowLeft') document.getElementById('ant').click(); if (e.key === 'ArrowRight') document.getElementById('prox').click(); };
document.getElementById('exp').onclick = () => { const L = ['path,revisada,x0,y0,x1,y1'];
  for (const d of DATA) { const r = reg(d); if (!r.caixas.length) L.push(`"${d.path}",${r.feito ? 'sim' : 'nao'},,,,`); for (const b of r.caixas) L.push(`"${d.path}",sim,${b.join(',')}`); }
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([L.join('\r\n') + '\r\n'], {type: 'text/csv'})); a.download = 'marcacoes.csv'; a.click(); };
mostrar();
</script></body></html>"""


def triagem(a):
    dados = RAIZ / a.dados; linhas = ler_manifesto(dados); SAI.mkdir(parents=True, exist_ok=True)
    print(f"Lendo os metadados de {len(linhas)} imagens...")
    meta = [{"path": l["path"]} | metadados(dados / l["path"]) for l in linhas]
    cams = [str(dados / l["path"]) for l in linhas]
    if a.teste_sem_modelo:
        rng = np.random.default_rng(0); notas = [dict(zip(FRASES, v / v.sum())) for v in rng.random((len(cams), 3)) ** 3]
    else:
        notas = notas_clip(cams, a.modelo)
    for m, s in zip(meta, notas):
        m["nota_rosto"], m["nota_placa"] = round(s["rosto"], 4), round(s["placa"], 4)
    cand = sorted((m for m in meta if max(m["nota_rosto"], m["nota_placa"]) >= a.limiar),
                  key=lambda m: -max(m["nota_rosto"], m["nota_placa"]))
    with (SAI / "metadados.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(meta[0]), lineterminator="\n"); w.writeheader(); w.writerows(meta)
    with (SAI / "candidatas.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(meta[0]), lineterminator="\n"); w.writeheader(); w.writerows(cand)
    dados_pag = [{"path": m["path"], "url": (dados / m["path"]).resolve().as_uri()} for m in cand]
    (SAI / "marcar.html").write_text(PAGINA.replace("__DATA__", json.dumps(dados_pag, ensure_ascii=False).replace("</", "<\\/")), encoding="utf-8")
    c = Counter(); [c.update(k for k in ("exif", "gps", "xmp", "texto") if m[k]) for m in meta]
    ori = sum(m["orientacao"] not in ("", "1") for m in meta)
    apar = Counter(m["aparelho"] for m in meta if m["aparelho"])
    res = [f"Etapa 16 (triagem) | {datetime.now(timezone.utc).isoformat(timespec='seconds')}" + (" | TESTE SEM MODELO" if a.teste_sem_modelo else ""),
           f"{len(meta)} imagens de {a.dados}", "",
           "Metadados encontrados (saem todos na exportação):",
           f"  com EXIF: {c['exif']} | com GPS: {c['gps']} | com XMP: {c['xmp']} | com texto embutido: {c['texto']}",
           f"  com orientação diferente de 1: {ori} (o treino leu os pixels sem girar; a cópia pública mantém os mesmos pixels)",
           f"  aparelhos distintos: {len(apar)}" + (f" (ex.: {', '.join(list(apar)[:3])})" if apar else ""), "",
           f"Candidatas a rosto ou placa (nota do CLIP ≥ {a.limiar}): {len(cand)}  -> abra marcar.html",
           "  O CLIP só escolhe as candidatas; quem marca o que borrar é uma pessoa."]
    (SAI / "resumo_triagem.txt").write_text("\n".join(res) + "\n", encoding="utf-8")
    print("\n".join(res)); print(f"\n[OK] {SAI}")


# ------------------------------------------------------------------ 3) exportar
def exportar(a):
    dados = RAIZ / a.dados; linhas = ler_manifesto(dados)
    destino = RAIZ / "data/publico" / f"ignis_alert_{a.versao}"
    if destino.exists():
        if not a.sobrescrever: sys.exit(f"[PARADO] {destino} já existe (use --sobrescrever).")
        shutil.rmtree(destino)
    caixas = {}
    if a.marcacoes:
        for r in csv.DictReader(open(a.marcacoes, encoding="utf-8-sig")):
            if r.get("x0"): caixas.setdefault(r["path"], []).append(tuple(int(float(r[k])) for k in ("x0", "y0", "x1", "y1")))
        print(f"Marcações: {sum(map(len, caixas.values()))} retângulos em {len(caixas)} imagens.")
    else:
        print("[AVISO] sem --marcacoes: só os metadados serão removidos (nenhum desfoque).")
    saida, cont = [], Counter()
    for l in linhas:
        orig = (dados / l["path"]).read_bytes()
        if l["path"] in caixas:
            with Image.open(io.BytesIO(orig)) as im:
                im = im.convert("RGB")
                for x0, y0, x1, y1 in caixas[l["path"]]:
                    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(im.width, x1), min(im.height, y1)
                    reg = im.crop((x0, y0, x1, y1)); raio = max(6, max(x1 - x0, y1 - y0) // 4)
                    im.paste(reg.filter(ImageFilter.GaussianBlur(raio)).filter(ImageFilter.GaussianBlur(raio)), (x0, y0))
                buf = io.BytesIO(); im.save(buf, "JPEG", quality=95); novo = buf.getvalue(); mud = "borrada"
        else:
            novo = sem_metadados(orig); mud = "metadados" if novo != orig else "nenhuma"
        cont[mud] += 1
        p = destino / l["path"]; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(novo)
        saida.append(l | {"sha256_treino": l["sha256"], "sha256": sha256(novo), "alteracao": mud})
    # conferência: nenhuma cópia pública pode ter EXIF, GPS ou texto
    falhas = [s["path"] for s in saida if any(metadados(destino / s["path"])[k] for k in ("exif", "gps", "xmp", "texto"))]
    cols = list(linhas[0]) + ["sha256_treino", "alteracao"]
    for arq in (destino / "split_manifest_publico.csv", SAI / f"split_manifest_publico_{a.versao}.csv"):
        arq.parent.mkdir(parents=True, exist_ok=True)
        with arq.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore", lineterminator="\n"); w.writeheader(); w.writerows(saida)
    for doc in ("DATASHEET.md", "GUIA_ROTULAGEM.md"):
        if (RAIZ / doc).exists(): shutil.copy2(RAIZ / doc, destino / doc)
    (destino / "VERSAO.txt").write_text(
        f"Ignis Alert dataset {a.versao}\nGerado em {datetime.now(timezone.utc).isoformat(timespec='seconds')} pela Etapa 16.\n"
        f"Imagens: {len(saida)} | só metadados removidos: {cont['metadados']} | borradas: {cont['borrada']} | sem mudança: {cont['nenhuma']}\n"
        "Fontes: phylake1337/fire-dataset (CC0) e cristiancristancho/forest-fire-image-dataset (licença a confirmar; ver DATASHEET.md).\n",
        encoding="utf-8")
    res = [f"Etapa 16 (exportação {a.versao}) | {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
           f"destino: {destino}",
           f"  imagens: {len(saida)} | metadados removidos sem recodificar: {cont['metadados']} | borradas: {cont['borrada']} | já limpas: {cont['nenhuma']}",
           f"  conferência de metadados nas cópias: {'OK, nenhuma tem EXIF, GPS, XMP ou texto' if not falhas else f'FALHOU em {len(falhas)}: ' + ', '.join(falhas[:5])}",
           f"  manifesto: split_manifest_publico.csv (SHA-256 do treino e da cópia pública)", "",
           f"Para marcar a versão no git:  git add relatorios/16_privacidade && git commit -m \"Dataset {a.versao}\" && git tag -a {a.versao} -m \"Dataset {a.versao}\" && git push --follow-tags"]
    (SAI / f"resumo_exportacao_{a.versao}.txt").write_text("\n".join(res) + "\n", encoding="utf-8")
    print("\n".join(res))
    if falhas: sys.exit(1)


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="passo", required=True)
    t = sub.add_parser("triagem"); t.add_argument("--dados", default="data/treino_ignis")
    t.add_argument("--modelo", default="openai/clip-vit-base-patch16"); t.add_argument("--limiar", type=float, default=0.25)
    t.add_argument("--teste-sem-modelo", action="store_true")
    e = sub.add_parser("exportar"); e.add_argument("--dados", default="data/treino_ignis"); e.add_argument("--marcacoes")
    e.add_argument("--versao", default="v1.0"); e.add_argument("--sobrescrever", action="store_true")
    a = ap.parse_args()
    triagem(a) if a.passo == "triagem" else exportar(a)


if __name__ == "__main__":
    main()
