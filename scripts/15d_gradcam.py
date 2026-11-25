#!/usr/bin/env python3
"""
Etapa 15d - ONDE A REDE OLHA (Grad-CAM; nenhuma imagem é alterada; nada é treinado).

Para cada imagem escolhida, o Grad-CAM pinta as regiões que mais empurraram a rede para "fogo". Entram:
  * TODOS os erros da rede no teste (falso alarme e fogo perdido);
  * uma amostra de acertos de cada classe (--por-classe, semente fixa);
  * opcional: os falsos alarmes dos negativos difíceis (--negativos, CSV predicoes_<rede>.csv da Etapa 14b).

Além das figuras, uma medida simples por imagem: que fração do "calor" do mapa cai em pixels com cor de chama
(laranja-amarelo, saturado e claro). Fração alta num falso alarme = a rede olhou para algo laranja que não era fogo.

Entradas: data/treino_ignis/ (Etapa 11), data/modelos/<rede>_torchvision/modelo.pth, relatorios/12_treino/
Saídas  : relatorios/15_robustez/gradcam_<rede>/ (grade_*.jpg, mapas/*.jpg, gradcam.csv, resumo.txt)
Uso:
  python scripts/15d_gradcam.py                                  (EfficientNet-B0, a rede escolhida)
  python scripts/15d_gradcam.py --negativos relatorios\\14_negativos\\resultado\\predicoes_efficientnet_b0.csv
"""
import argparse, csv, importlib.util, json, random, sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parent.parent
CAMADA = {"efficientnet_b0": lambda m: m.features[-1], "resnet18": lambda m: m.layer4[-1],
          "densenet121": lambda m: m.features.denseblock4}


def t12():
    spec = importlib.util.spec_from_file_location("treino12", RAIZ / "scripts" / "12_treinar.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def cor_quente(c):
    """mapa 0..1 -> RGB (preto-azul-amarelo-vermelho, sem depender do matplotlib)."""
    pts = np.array([0, .35, .7, 1.0]); cores = np.array([[20, 20, 60], [40, 90, 200], [250, 220, 60], [230, 40, 20]], float)
    return np.stack([np.interp(c, pts, cores[:, k]) for k in range(3)], -1).astype(np.uint8)


def pixels_chama(rgb):
    hsv = np.asarray(Image.fromarray(rgb).convert("HSV"), dtype=np.float32) / 255
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    return ((h < 0.14) | (h > 0.95)) & (s > 0.45) & (v > 0.55)


def grade(itens, arq, titulo, col=4, lado=300):
    if not itens: return
    fonte = ImageFont.load_default(size=14)
    lin = (len(itens) + col - 1) // col
    G = Image.new("RGB", (col * 2 * lado, 40 + lin * (lado + 34)), (251, 250, 246)); d = ImageDraw.Draw(G)
    d.text((10, 12), titulo, fill=(15, 31, 25), font=fonte)
    for k, it in enumerate(itens):
        x, y = (k % col) * 2 * lado, 40 + (k // col) * (lado + 34)
        G.paste(it["orig"].resize((lado, lado)), (x, y)); G.paste(it["sobre"].resize((lado, lado)), (x + lado, y))
        d.text((x + 4, y + lado + 4), f"{it['grupo']} | p(fogo)={it['p']:.2f} | calor em cor de chama {it['frac']:.0%}", fill=(15, 31, 25), font=fonte)
        d.text((x + 4, y + lado + 18), it["path"][-70:], fill=(90, 107, 99), font=fonte)
    G.save(arq, quality=88)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dados", default="data/treino_ignis")
    ap.add_argument("--rede", default="efficientnet_b0", choices=list(CAMADA))
    ap.add_argument("--sufixo", default="torchvision")
    ap.add_argument("--por-classe", type=int, default=8, help="acertos sorteados de cada classe")
    ap.add_argument("--negativos", help="predicoes_<rede>.csv da Etapa 14b (entra cada falso alarme)")
    ap.add_argument("--semente", type=int, default=42)
    a = ap.parse_args()
    import torch
    T = t12(); pasta = RAIZ / a.dados; nome = f"{a.rede}_{a.sufixo}"
    pesos = RAIZ / "data/modelos" / nome / "modelo.pth"; cfg = RAIZ / "relatorios/12_treino" / nome / "config.json"
    if not pesos.exists() or not cfg.exists(): sys.exit(f"[PARADO] faltam pesos ou config de {nome} (Etapa 12).")
    limiar = json.loads(cfg.read_text(encoding="utf-8"))["limiar_calibrado_na_validacao"]
    m = T.criar_rede(a.rede, pre_treinada=False); m.load_state_dict(torch.load(pesos, map_location="cpu")["estado"]); m.eval()
    sai = RAIZ / "relatorios/15_robustez" / f"gradcam_{a.rede}"; (sai / "mapas").mkdir(parents=True, exist_ok=True)

    # escolhe as imagens: erros do teste + amostra de acertos (pelas predições gravadas na Etapa 12)
    pred = list(csv.DictReader((RAIZ / "relatorios/12_treino" / nome / "predicoes_teste.csv").open(encoding="utf-8")))
    rng = random.Random(a.semente); alvos = []
    for r in pred:
        if r["acertou"] != "sim":
            alvos.append((pasta / r["path"], r["path"], "falso alarme" if r["classe_real"] == "NoFire" else "fogo perdido"))
    for classe, grupo in (("Fire", "acerto com fogo"), ("NoFire", "acerto sem fogo")):
        ok = [r for r in pred if r["acertou"] == "sim" and r["classe_real"] == classe]
        alvos += [(pasta / r["path"], r["path"], grupo) for r in rng.sample(ok, min(a.por_classe, len(ok)))]
    if a.negativos:
        orig = Path(json.loads((RAIZ / "relatorios/14_negativos/origem.json").read_text(encoding="utf-8"))["caminho_local"])
        for r in csv.DictReader(open(a.negativos, encoding="utf-8")):
            if r.get("alarme_falso") == "sim":
                alvos.append((orig / Path(*r["caminho_relativo"].replace("\\", "/").split("/")), r["caminho_relativo"], f"negativo difícil: {r['cena']}"))

    ativ, grad = {}, {}
    camada = CAMADA[a.rede](m)
    def gancho(mod, i, o):   # guarda a ativação e o gradiente dela (sem hook de backward no módulo)
        ativ["a"] = o; o.register_hook(lambda g: grad.__setitem__("g", g))
    camada.register_forward_hook(gancho)
    _, aval = T.transformacoes(224, "nenhum")
    itens = []
    for k, (arq, rot, grupo) in enumerate(alvos):
        with Image.open(arq) as im: im = im.convert("RGB")
        x = aval(im).unsqueeze(0)
        m.zero_grad(); out = m(x); p = torch.softmax(out, 1)[0, 1].item(); out[0, 1].backward()
        A, G = ativ["a"][0].detach(), grad["g"][0].detach()
        cam = torch.relu((G.mean((1, 2), keepdim=True) * A).sum(0)).numpy()
        cam = cam / (cam.max() + 1e-9)
        # a mesma região que a rede viu: redimensiona e corta o centro como na avaliação
        lado = round(224 * 256 / 224); w0, h0 = im.size; s = lado / min(w0, h0)
        vis = im.resize((round(w0 * s), round(h0 * s)))
        l0, t0 = (vis.width - 224) // 2, (vis.height - 224) // 2; vis = vis.crop((l0, t0, l0 + 224, t0 + 224))
        mapa = np.asarray(Image.fromarray((cam * 255).astype(np.uint8)).resize((224, 224), Image.BILINEAR), dtype=np.float32) / 255
        rgb = np.asarray(vis); sobre = (0.55 * rgb + 0.45 * cor_quente(mapa)).astype(np.uint8)
        frac = float((mapa * pixels_chama(rgb)).sum() / (mapa.sum() + 1e-9))
        it = {"path": rot, "grupo": grupo, "p": p, "frac": frac, "orig": vis, "sobre": Image.fromarray(sobre)}
        it["sobre"].save(sai / "mapas" / f"{k:03d}.jpg", quality=88); itens.append(it)
        print(f"  Grad-CAM {k + 1}/{len(alvos)}", end="\r")
    print()

    with (sai / "gradcam.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n"); w.writerow(["mapa", "path", "grupo", "prob_fogo", "alarme", "calor_em_cor_de_chama"])
        for k, it in enumerate(itens):
            w.writerow([f"mapas/{k:03d}.jpg", it["path"], it["grupo"], round(it["p"], 4), "sim" if it["p"] >= limiar else "", round(it["frac"], 3)])
    grupos = sorted({it["grupo"] for it in itens})
    for gname in ["falso alarme", "fogo perdido"]:
        grade([it for it in itens if it["grupo"] == gname], sai / f"grade_{gname.replace(' ', '_')}.jpg", f"{a.rede}: {gname}")
    grade([it for it in itens if it["grupo"].startswith("acerto")], sai / "grade_acertos.jpg", f"{a.rede}: acertos sorteados")
    grade([it for it in itens if it["grupo"].startswith("negativo")], sai / "grade_negativos_dificeis.jpg", f"{a.rede}: falsos alarmes em negativos difíceis")
    res = [f"Etapa 15d | {datetime.now(timezone.utc).isoformat(timespec='seconds')} | Grad-CAM {a.rede} (limiar {limiar:.4f})", "",
           f"  {'grupo':<34} {'imagens':>7} {'calor médio em cor de chama':>29}"]
    for gname in grupos:
        fs = [it["frac"] for it in itens if it["grupo"] == gname]
        res.append(f"  {gname:<34} {len(fs):>7} {100 * np.mean(fs):>28.0f}%")
    res += ["", "Leitura: nos acertos com fogo o calor deve cair na chama. Num falso alarme com calor alto em cor de chama,",
            "a rede reagiu a algo laranja (sol, luz, folhas); com calor baixo, a pista foi outra (fumaça, textura).",
            "As figuras estão em grade_*.jpg (original à esquerda, mapa à direita)."]
    (sai / "resumo.txt").write_text("\n".join(res) + "\n", encoding="utf-8")
    print("\n".join(res)); print(f"\n[OK] {sai}")


if __name__ == "__main__":
    main()
