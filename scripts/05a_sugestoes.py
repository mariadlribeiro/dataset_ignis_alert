#!/usr/bin/env python3
"""
Etapa 5a - SUGESTÕES de ambiente, fogo, fumaça e tipo de câmera com CLIP (zero-shot).

IMPORTANTE: o modelo NÃO decide nada. Ele só sugere; quem confirma é você (revisao.csv).
  * o nome da pasta original NÃO é usado pelo modelo (só depois, para detectar discordâncias);
  * nada no dataset é alterado; tudo é gravado em relatorios/05_sugestoes/.

Saídas:
  sugestoes.csv   -> uma linha por imagem: sugestões, probabilidades e motivos de revisão
  revisao.csv     -> só as imagens que precisam de revisão (+ amostra de auditoria), com colunas
                     *_confirmado EM BRANCO para você preencher. (Não é sobrescrito se já existir.)
  folhas/*.png    -> folhas de contato na ordem do revisao.csv (coluna n = número na miniatura)
  metadados.json  -> modelo, versões e limiares usados (reprodutibilidade)

Uso:
  python scripts/05a_sugestoes.py
  python scripts/05a_sugestoes.py --modelo openai/clip-vit-base-patch16
"""
import argparse, csv, hashlib, json, platform, random
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw

AMBIENTES = {
    "floresta": ["a photo of a forest with trees", "a photo of woodland vegetation",
                 "a landscape of a forest seen from a distance"],
    "cidade": ["a photo of a city street", "a photo of an urban neighborhood",
               "a photo of a public space in a town"],
    "casa": ["a photo of a house", "a photo of the inside of a home", "a photo of a residential yard"],
    "predios": ["a photo of a tall commercial building", "a photo of an industrial building or factory",
                "a photo of a skyscraper"],
    "flores_jardins": ["a photo of flowers", "a photo of a garden", "a photo of ornamental plants"],
    "outros": ["a photo of an open field or grassland", "a photo of a mountain or a lake",
               "a photo of a vehicle or an object", "a photo of a person"],
}
FOGO = (["a photo with visible flames", "a photo of a burning fire", "a photo of a fire with orange flames"],
        ["a photo with no fire", "a photo of a calm scene without flames", "a photo of an ordinary landscape"])
FUMACA = (["a photo with visible smoke", "a photo of a smoke plume", "a photo of haze and smoke in the air"],
          ["a photo with clear air and no smoke", "a photo of a clear sky", "a photo of an ordinary landscape"])
CAMERAS = {
    "satelite": ["a satellite image from space"],
    "drone": ["an aerial photo taken by a drone"],
    "vigilancia": ["a photo from a fixed surveillance camera"],
    "celular_terrestre": ["a photo taken by a person with a phone at ground level"],
}
LIM = {"amb_conf_min": 0.45, "amb_margem_min": 0.15, "p_sim": 0.80, "p_nao": 0.20, "fumaca_revisar": 0.50}
MINIATURA, COLS, LINS = 200, 6, 5


# ---------------------------------------------------------------- modelo
def prever_clip(caminhos, nome_modelo, lote=16):
    import torch
    from transformers import CLIPModel, CLIPProcessor
    disp = "cuda" if torch.cuda.is_available() else "cpu"
    modelo = CLIPModel.from_pretrained(nome_modelo).to(disp).eval()
    proc = CLIPProcessor.from_pretrained(nome_modelo)
    escala = modelo.logit_scale.exp().item()

    def emb_texto(frases):
        with torch.no_grad():
            t = proc(text=frases, return_tensors="pt", padding=True).to(disp)
            e = modelo.text_projection(modelo.text_model(input_ids=t["input_ids"], attention_mask=t["attention_mask"]).pooler_output); e = e / e.norm(dim=-1, keepdim=True)
        m = e.mean(dim=0); return m / m.norm()

    E_amb = torch.stack([emb_texto(v) for v in AMBIENTES.values()])
    E_fogo = torch.stack([emb_texto(v) for v in FOGO])
    E_fum = torch.stack([emb_texto(v) for v in FUMACA])
    E_cam = torch.stack([emb_texto(v) for v in CAMERAS.values()])

    saidas = []
    for k in range(0, len(caminhos), lote):
        imgs = []
        for p in caminhos[k:k + lote]:
            with Image.open(p) as im:
                imgs.append(im.convert("RGB").copy())
        with torch.no_grad():
            x = proc(images=imgs, return_tensors="pt").to(disp)
            e = modelo.visual_projection(modelo.vision_model(pixel_values=x["pixel_values"]).pooler_output); e = e / e.norm(dim=-1, keepdim=True)
            sm = lambda E: (escala * e @ E.T).softmax(dim=-1).cpu().tolist()
            a, f, u, c = sm(E_amb), sm(E_fogo), sm(E_fum), sm(E_cam)
        for i in range(len(imgs)):
            saidas.append({"amb": a[i], "fogo": f[i][0], "fumaca": u[i][0], "cam": c[i]})
        print(f"  {min(k + lote, len(caminhos))}/{len(caminhos)}", end="\r")
    print()
    import transformers
    return saidas, {"modelo": nome_modelo, "dispositivo": disp, "torch": torch.__version__,
                    "transformers": transformers.__version__}


def prever_falso(caminhos):
    """SÓ PARA TESTAR O PIPELINE (sem modelo). Probabilidades aleatórias e determinísticas."""
    saidas = []
    for p in caminhos:
        r = random.Random(int(hashlib.md5(str(p).encode()).hexdigest(), 16))
        def dist(n):
            v = [r.random() ** 2 for _ in range(n)]; s = sum(v); return [x / s for x in v]
        saidas.append({"amb": dist(len(AMBIENTES)), "fogo": r.random(), "fumaca": r.random(), "cam": dist(len(CAMERAS))})
    return saidas, {"modelo": "FALSO (apenas teste)"}


# ---------------------------------------------------------------- utilidades
def ler(caminho):
    with open(caminho, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def gravar(caminho, linhas, cols):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(linhas)


def tri(p):
    return "sim" if p >= LIM["p_sim"] else ("nao" if p <= LIM["p_nao"] else "incerto")


def folha(itens, destino):
    img = Image.new("RGB", (COLS * MINIATURA, LINS * (MINIATURA + 16)), "white")
    d = ImageDraw.Draw(img)
    for i, (p, rotulo) in enumerate(itens):
        x, y = (i % COLS) * MINIATURA, (i // COLS) * (MINIATURA + 16)
        try:
            with Image.open(p) as im:
                im = im.convert("RGB"); im.thumbnail((MINIATURA - 4, MINIATURA - 4)); img.paste(im, (x + 2, y + 2))
        except Exception:
            d.rectangle([x + 2, y + 2, x + MINIATURA - 2, y + MINIATURA - 2], outline="red")
        d.text((x + 3, y + MINIATURA), rotulo[:34], fill="black")
    img.save(destino)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--origem", default="relatorios/01_origem/origem.json")
    ap.add_argument("--grupos", default="relatorios/03_duplicatas/imagem_grupo.csv")
    ap.add_argument("--divisao", default="relatorios/04_divisao/divisao.csv")
    ap.add_argument("--pendentes", default="relatorios/04_divisao/pendentes.csv")
    ap.add_argument("--saida", default="relatorios/05_sugestoes")
    ap.add_argument("--modelo", default="openai/clip-vit-base-patch16")
    ap.add_argument("--auditoria", type=float, default=0.10, help="fração das imagens 'seguras' a revisar")
    ap.add_argument("--semente", type=int, default=42)
    ap.add_argument("--forcar", action="store_true", help="permite sobrescrever revisao.csv")
    ap.add_argument("--teste-sem-modelo", action="store_true", help="só para testar o pipeline")
    a = ap.parse_args()

    raiz = Path(json.loads(Path(a.origem).read_text(encoding="utf-8"))["caminho_local"])
    saida = Path(a.saida); (saida / "folhas").mkdir(parents=True, exist_ok=True)
    imagens = ler(a.grupos)
    split = {r["caminho_relativo"]: r["split"] for r in ler(a.divisao)} if Path(a.divisao).exists() else {}
    pend = {r["caminho_relativo"]: r["motivo"] for r in ler(a.pendentes)} if Path(a.pendentes).exists() else {}
    caminhos = [raiz / r["caminho_relativo"] for r in imagens]

    print(f"Imagens: {len(caminhos)} | modelo: {'(teste)' if a.teste_sem_modelo else a.modelo}")
    pred, meta = prever_falso(caminhos) if a.teste_sem_modelo else prever_clip(caminhos, a.modelo)

    nomes_amb, nomes_cam = list(AMBIENTES), list(CAMERAS)
    linhas = []
    for r, p in zip(imagens, pred):
        ordem = sorted(range(len(nomes_amb)), key=lambda i: -p["amb"][i])
        top1, top2 = ordem[0], ordem[1]
        conf, margem = p["amb"][top1], p["amb"][top1] - p["amb"][top2]
        amb = nomes_amb[top1] if (conf >= LIM["amb_conf_min"] and margem >= LIM["amb_margem_min"]) else "ambiente_incerto"
        fogo, fumaca = tri(p["fogo"]), tri(p["fumaca"])
        ic = max(range(len(nomes_cam)), key=lambda i: p["cam"][i])
        motivos = []
        if amb == "ambiente_incerto": motivos.append("ambiente_incerto")
        if fogo == "incerto": motivos.append("fogo_incerto")
        if p["fumaca"] >= LIM["fumaca_revisar"] and fogo != "sim": motivos.append("fumaca_sem_fogo")
        pasta_fogo = "non_fire" not in r["classe_original"].lower()
        if (pasta_fogo and p["fogo"] < 0.5) or (not pasta_fogo and p["fogo"] >= 0.5):
            motivos.append("discorda_da_pasta")
        if r["caminho_relativo"] in pend: motivos.append("pendente_etapa4")
        linhas.append({
            "caminho_relativo": r["caminho_relativo"], "classe_original": r["classe_original"],
            "id_grupo": r["id_grupo"], "split": split.get(r["caminho_relativo"], ""),
            "ambiente_sugerido": amb, "amb_top1": nomes_amb[top1], "amb_conf": round(conf, 3),
            "amb_top2": nomes_amb[top2], "amb_margem": round(margem, 3),
            "fogo_sugerido": fogo, "fogo_prob": round(p["fogo"], 3),
            "fumaca_sugerida": fumaca, "fumaca_prob": round(p["fumaca"], 3),
            "camera_sugerida_fraca": nomes_cam[ic], "camera_conf": round(p["cam"][ic], 3),
            "motivos_revisao": ";".join(motivos)})

    # amostra de auditoria entre as "seguras" (mede a precisão real do modelo neste dataset)
    seguras = [l for l in linhas if not l["motivos_revisao"]]
    rnd = random.Random(a.semente)
    for l in rnd.sample(seguras, int(len(seguras) * a.auditoria)):
        l["motivos_revisao"] = "auditoria"
    for l in linhas: l["revisar"] = bool(l["motivos_revisao"])

    cols = list(linhas[0].keys())
    gravar(saida / "sugestoes.csv", linhas, cols)

    rev = [l for l in linhas if l["revisar"]]
    rev.sort(key=lambda l: (l["motivos_revisao"] == "auditoria", l["motivos_revisao"], l["caminho_relativo"]))
    saida_rev = []
    for n, l in enumerate(rev, 1):
        saida_rev.append({"n": n, "caminho_relativo": l["caminho_relativo"], "classe_original": l["classe_original"],
                          "motivos_revisao": l["motivos_revisao"], "ambiente_sugerido": l["ambiente_sugerido"],
                          "fogo_sugerido": l["fogo_sugerido"], "fumaca_sugerida": l["fumaca_sugerida"],
                          "ambiente_confirmado": "", "fogo_confirmado": "", "fumaca_confirmada": "",
                          "camera_confirmada": "", "observacao": ""})
    destino_rev = saida / "revisao.csv"
    if destino_rev.exists() and not a.forcar:
        destino_rev = saida / "revisao_novo.csv"
        print(f"AVISO: revisao.csv já existe e NÃO foi sobrescrito (suas anotações estão seguras). Nova versão em {destino_rev.name}")
    gravar(destino_rev, saida_rev, list(saida_rev[0].keys()))

    por = COLS * LINS
    for k in range(0, len(saida_rev), por):
        folha([(raiz / s["caminho_relativo"], f"{s['n']}. {Path(s['caminho_relativo']).stem}")
               for s in saida_rev[k:k + por]], saida / "folhas" / f"revisao_{k // por + 1:02d}.png")

    meta.update({"limiares": LIM, "auditoria": a.auditoria, "semente": a.semente, "python": platform.python_version(),
                 "prompts": {"ambientes": AMBIENTES, "fogo": FOGO, "fumaca": FUMACA, "cameras": CAMERAS}})
    (saida / "metadados.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\nAmbiente sugerido:", dict(Counter(l["ambiente_sugerido"] for l in linhas)))
    print("Fogo sugerido    :", dict(Counter(l["fogo_sugerido"] for l in linhas)))
    print("Fumaça sugerida  :", dict(Counter(l["fumaca_sugerida"] for l in linhas)))
    print("Fogo x pasta     :", dict(Counter((l["classe_original"].split("/")[-1], l["fogo_sugerido"]) for l in linhas)))
    mot = Counter(m for l in linhas for m in l["motivos_revisao"].split(";") if m)
    print("Motivos de revisão:", dict(mot))
    print(f"Imagens para revisar: {len(rev)} de {len(linhas)}. Nada foi alterado no dataset.")


if __name__ == "__main__":
    main()

