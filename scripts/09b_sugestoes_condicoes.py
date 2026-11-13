#!/usr/bin/env python3
"""
Etapa 9b - SUGESTÕES de condição da imagem com CLIP (zero-shot): ponto de vista, distância do fogo, pessoas,
veículos, texto/marca d'água e o principal elemento que pode confundir (pôr do sol, luz artificial, reflexo, neblina).

(A iluminação, clara/média/escura, não passa pelo CLIP: é medida pelo brilho na Etapa 9a.)

IMPORTANTE: como na Etapa 5a, o modelo NÃO decide nada; só sugere. Quem confirma é você, na página da 9c.
  * só entram as imagens incluídas na divisão (situacao = incluida no inventário);
  * a distância do fogo só é perguntada quando fogo = sim; nas outras fica "nao_se_aplica";
  * nada no dataset é alterado; tudo é gravado em relatorios/09_condicoes/.

Por que esses atributos: são condições que a aumentação de dados NÃO cria. Girar ou recortar uma foto
tirada do chão não a transforma em vista aérea; e um recorte aleatório pode cortar justamente um fogo
pequeno e distante, deixando o rótulo errado.

Saídas:
  sugestoes_condicoes.csv -> uma linha por imagem: sugestões, confiança, margem e motivos de revisão
  revisao_condicoes.csv   -> só as imagens a revisar (sugestão duvidosa + amostra de auditoria cega),
                             com colunas *_confirmado em branco. (Não é sobrescrito se já existir.)
  metadados_condicoes.json -> modelo, versões, frases e limiares (reprodutibilidade)

Uso:  python scripts/09b_sugestoes_condicoes.py
      python scripts/09b_sugestoes_condicoes.py --forcar --excluir-auditoria relatorios/09_condicoes/auditoria_anterior.csv relatorios/09_condicoes/revisao_condicoes_preenchida_tentativa2.csv
            (sorteia uma auditoria NOVA, sem as imagens listadas: elas já foram vistas e não servem mais como cegas)
      python scripts/09b_sugestoes_condicoes.py --teste-sem-modelo   # só para testar o pipeline
"""
import argparse, csv, hashlib, json, platform, random
from collections import Counter
from pathlib import Path

from PIL import Image

ATRIBUTOS = {
    "ponto_vista": {
        "chao": ["a photo taken from the ground at eye level", "a photo taken by a person standing on the ground"],
        "elevado": ["a wide view from a high fixed camera or a watchtower", "a photo taken from a hilltop overlooking the landscape"],
        "aereo": ["an aerial photo taken from a drone or an aircraft", "a bird's eye view from directly above"],
        "satelite": ["a satellite image of the earth from space"],
    },
    "distancia_fogo": {
        "perto": ["a close-up of flames filling the frame", "a photo of flames at close range"],
        "medio": ["a fire a short distance away with its surroundings visible", "a burning building or trees seen from across the street"],
        "distante": ["a distant fire far away on the horizon", "a small fire and smoke far away in a wide landscape"],
    },
    # elementos que podem virar "atalho" para o modelo (ex.: bombeiro = fogo) ou vazar a origem (marca d'água)
    "pessoas": {
        "sim": ["a photo with people or firefighters in it", "a photo showing a person"],
        "nao": ["a photo with no people in it", "an empty scene without any person"],
    },
    "veiculos": {
        "sim": ["a photo with a car, a truck, a fire engine or a helicopter", "a photo showing a vehicle"],
        "nao": ["a photo with no vehicles in it", "a scene without any car or truck"],
    },
    "texto": {
        "sim": ["a photo with text, a caption, a logo or a watermark on it", "an image with written words overlaid on it"],
        "nao": ["a clean photo with no text and no watermark", "a photo without any writing on it"],
    },
    "hora_dia": {
        "dia": ["a photo taken during the day in daylight", "a daytime outdoor scene"],
        "noite": ["a photo taken at night", "a night scene with a dark sky"],
        "entardecer": ["a photo taken at dusk or dawn", "a twilight scene at sunset"],
    },
    "ceu": {
        "sim": ["a photo where the sky is visible", "a scene with sky above the horizon"],
        "nao": ["a close-up photo with no sky visible", "a scene where the sky cannot be seen"],
    },
    "vegetacao": {
        "floresta_densa": ["a dense forest with many trees", "a thick woodland"],
        "campo": ["a grassland, savanna or pasture", "dry grass and low shrubs in a field"],
        "urbana": ["street trees, a garden or a lawn in a city", "a few trees in an urban area"],
        "sem_vegetacao": ["a scene with no plants or trees", "buildings and streets without vegetation"],
    },
    "agua": {
        "sim": ["a photo with water, a river, a lake or the sea", "a photo with a water jet from a fire hose"],
        "nao": ["a photo with no water visible", "a dry scene without water"],
    },
    "tipo_fogo": {
        "florestal": ["a forest fire burning trees", "a wildfire in the woods"],
        "estrutura": ["a burning building or house", "a structure fire"],
        "veiculo": ["a burning car or truck", "a vehicle on fire"],
        "campo": ["a grass fire in a field", "a burning pasture or crop field"],
        "controlado": ["a campfire, a candle or a stove flame", "a small controlled fire"],
        "outro": ["a burning pile of trash or an explosion", "a fire of another kind"],
    },
    # o principal elemento que pode CONFUNDIR o modelo (parece fogo ou esconde o fogo)
    "confusor": {
        "nenhum": ["an ordinary photo with nothing unusual", "a plain scene"],
        "por_do_sol": ["a photo of a sunset or a sunrise with an orange sky", "the sun low on the horizon with a red sky"],
        "luz_artificial": ["a photo with bright orange artificial lights or street lamps", "city lights glowing at night"],
        "reflexo": ["light or fire reflected on water or glass", "a reflection on a lake or a window"],
        "neblina": ["a photo with fog, mist or haze", "a hazy scene with low visibility"],
    },
}
BINARIOS = {"pessoas", "veiculos", "texto", "ceu", "agua"}
SO_FOGO = {"distancia_fogo", "tipo_fogo"}
# atributos só humanos (o CLIP não ajuda): entram na revisão sem palpite
SEM_MODELO = {"focos": ["um", "varios"], "cor_chamas": ["amarela", "laranja", "vermelha", "azulada", "mista"],
              "encoberto": ["nao", "fumaca", "vegetacao", "pessoas_objetos"]}
LIM = {"conf_min": 0.50, "margem_min": 0.15, "conf_min_binario": 0.70}


def prever_clip(caminhos, nome_modelo, lote=16):
    try:
        import torch  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("PyTorch não está instalado no ambiente usado para rodar este script.") from exc
    from transformers import CLIPModel, CLIPProcessor
    disp = "cuda" if torch.cuda.is_available() else "cpu"
    modelo = CLIPModel.from_pretrained(nome_modelo).to(disp).eval()
    proc = CLIPProcessor.from_pretrained(nome_modelo)
    escala = modelo.logit_scale.exp().item()

    def emb_texto(frases):
        with torch.no_grad():
            t = proc(text=frases, return_tensors="pt", padding=True).to(disp)
            e = modelo.text_projection(modelo.text_model(input_ids=t["input_ids"], attention_mask=t["attention_mask"]).pooler_output)
            e = e / e.norm(dim=-1, keepdim=True)
        m = e.mean(dim=0); return m / m.norm()

    E = {a: torch.stack([emb_texto(f) for f in ops.values()]) for a, ops in ATRIBUTOS.items()}
    saidas = []
    for k in range(0, len(caminhos), lote):
        imgs = []
        for p in caminhos[k:k + lote]:
            with Image.open(p) as im:
                im.seek(0); imgs.append(im.convert("RGB").copy())
        with torch.no_grad():
            x = proc(images=imgs, return_tensors="pt").to(disp)
            e = modelo.visual_projection(modelo.vision_model(pixel_values=x["pixel_values"]).pooler_output)
            e = e / e.norm(dim=-1, keepdim=True)
            res = {a: (escala * e @ M.T).softmax(dim=-1).cpu().tolist() for a, M in E.items()}
        for i in range(len(imgs)):
            saidas.append({a: res[a][i] for a in ATRIBUTOS})
        print(f"  {min(k + lote, len(caminhos))}/{len(caminhos)}", end="\r")
    print()
    import transformers
    return saidas, {"modelo": nome_modelo, "dispositivo": disp, "torch": torch.__version__, "transformers": transformers.__version__}


def prever_falso(caminhos):
    """SÓ PARA TESTAR O PIPELINE (sem modelo): probabilidades aleatórias e determinísticas."""
    saidas = []
    for p in caminhos:
        r = random.Random(int(hashlib.md5(str(p).encode()).hexdigest(), 16))
        def dist(n):
            v = [r.random() ** 3 for _ in range(n)]; s = sum(v); return [x / s for x in v]
        saidas.append({a: dist(len(ops)) for a, ops in ATRIBUTOS.items()})
    return saidas, {"modelo": "FALSO (apenas teste)"}


def ler(caminho):
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def gravar(caminho, linhas, cols):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(linhas)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--origem", default="relatorios/01_origem/origem.json")
    ap.add_argument("--inventario", default="relatorios/06_plano/inventario.csv")
    ap.add_argument("--saida", default="relatorios/09_condicoes")
    ap.add_argument("--modelo", default="openai/clip-vit-base-patch16")
    ap.add_argument("--auditoria", type=float, default=0.10, help="fração das imagens 'seguras' para a auditoria cega")
    ap.add_argument("--semente", type=int, default=42)
    ap.add_argument("--forcar", action="store_true", help="permite sobrescrever revisao_condicoes.csv")
    ap.add_argument("--teste-sem-modelo", action="store_true")
    ap.add_argument("--revisar-todas", action="store_true", help="coloca TODAS as imagens na revisão (motivo 'completa')")
    ap.add_argument("--manter-auditoria", help="revisao_condicoes.csv anterior: reusa EXATAMENTE a mesma amostra cega "
                    "(para acrescentar atributos sem trocar as imagens de auditoria)")
    ap.add_argument("--excluir-auditoria", nargs="+", default=[],
                    help="CSVs com coluna caminho_original: imagens que NÃO podem entrar na amostra cega "
                         "(se o CSV tiver motivos_revisao, só as linhas de auditoria contam)")
    a = ap.parse_args()

    raiz = Path(json.loads(Path(a.origem).read_text(encoding="utf-8"))["caminho_local"])
    inv = sorted((r for r in ler(a.inventario) if r["situacao"] == "incluida"), key=lambda r: r["caminho_original"])
    caminhos = [raiz / r["caminho_original"].replace("\\", "/") for r in inv]
    print(f"Imagens: {len(inv)} | modelo: {'(teste)' if a.teste_sem_modelo else a.modelo}")
    pred, meta = prever_falso(caminhos) if a.teste_sem_modelo else prever_clip(caminhos, a.modelo)

    linhas = []
    for r, p in zip(inv, pred):
        l = {"caminho_original": r["caminho_original"], "split": r["split"], "ambiente": r["ambiente"], "fogo": r["fogo"]}
        motivos = []
        for atr, ops in ATRIBUTOS.items():
            if atr in SO_FOGO and r["fogo"] != "sim":
                l.update({f"{atr}_sugerido": "nao_se_aplica", f"{atr}_conf": "", f"{atr}_2a": "", f"{atr}_margem": ""})
                continue
            nomes = list(ops)
            ordem = sorted(range(len(nomes)), key=lambda i: -p[atr][i])
            c, m = p[atr][ordem[0]], p[atr][ordem[0]] - p[atr][ordem[1]]
            seguro = (c >= LIM["conf_min_binario"]) if atr in BINARIOS else (c >= LIM["conf_min"] and m >= LIM["margem_min"])
            l.update({f"{atr}_sugerido": nomes[ordem[0]] if seguro else "incerto", f"{atr}_top1": nomes[ordem[0]],
                      f"{atr}_conf": round(c, 3), f"{atr}_2a": nomes[ordem[1]], f"{atr}_margem": round(m, 3)})
            if not seguro: motivos.append(f"{atr}_incerto")
        for atr in SEM_MODELO:
            v = "nao_se_aplica" if r["fogo"] != "sim" else ""
            l.update({f"{atr}_sugerido": v, f"{atr}_top1": "", f"{atr}_conf": "", f"{atr}_2a": "", f"{atr}_margem": ""})
        l["motivos_revisao"] = ";".join(motivos)
        linhas.append(l)

    vistas = {r["caminho_original"] for f in a.excluir_auditoria for r in ler(f)
              if r.get("motivos_revisao", "auditoria") == "auditoria"}
    seguras = [l for l in linhas if not l["motivos_revisao"] and l["caminho_original"] not in vistas]
    if vistas:
        print(f"Auditoria: {len(vistas)} imagens já vistas ficaram fora do sorteio.")
    if a.manter_auditoria:
        manter = {r["caminho_original"] for r in ler(a.manter_auditoria) if r["motivos_revisao"] == "auditoria"}
        achadas = [l for l in linhas if l["caminho_original"] in manter]
        if len(achadas) != len(manter):
            raise SystemExit(f"--manter-auditoria: {len(manter) - len(achadas)} imagens da auditoria anterior não estão mais incluídas.")
        for l in achadas:
            l["motivos_revisao"] = "auditoria"
        print(f"Auditoria: mantidas as mesmas {len(achadas)} imagens cegas de {a.manter_auditoria}.")
    else:
        for l in random.Random(a.semente).sample(seguras, int(len(seguras) * a.auditoria)):
            l["motivos_revisao"] = "auditoria"
    if a.revisar_todas:
        for l in linhas:
            if not l["motivos_revisao"]:
                l["motivos_revisao"] = "completa"
    cols = ["caminho_original", "split", "ambiente", "fogo"]
    for atr in list(ATRIBUTOS) + list(SEM_MODELO):
        cols += [f"{atr}_sugerido", f"{atr}_top1", f"{atr}_conf", f"{atr}_2a", f"{atr}_margem"]
    cols.append("motivos_revisao")
    saida = Path(a.saida); saida.mkdir(parents=True, exist_ok=True)
    gravar(saida / "sugestoes_condicoes.csv", linhas, cols)

    rev = sorted((l for l in linhas if l["motivos_revisao"]),
                 key=lambda l: (l["motivos_revisao"] == "auditoria", l["motivos_revisao"], l["caminho_original"]))
    out = []
    for n, l in enumerate(rev, 1):
        o = {"n": n, "caminho_original": l["caminho_original"], "motivos_revisao": l["motivos_revisao"]}
        for atr in list(ATRIBUTOS) + list(SEM_MODELO):
            o[f"{atr}_sugerido"] = l[f"{atr}_sugerido"]
        for atr in list(ATRIBUTOS) + list(SEM_MODELO):
            o[f"{atr}_confirmado"] = ""
        o["observacao"] = ""
        out.append(o)
    destino = saida / "revisao_condicoes.csv"
    if destino.exists() and not a.forcar:
        destino = saida / "revisao_condicoes_novo.csv"
        print(f"AVISO: revisao_condicoes.csv já existe e NÃO foi sobrescrito. Nova versão em {destino.name}")
    gravar(destino, out, list(out[0].keys()))

    meta.update({"limiares": LIM, "auditoria": a.auditoria, "semente": a.semente, "python": platform.python_version(),
                 "prompts": ATRIBUTOS})
    (saida / "metadados_condicoes.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    for atr in ATRIBUTOS:
        print(f"{atr:15s}", dict(Counter(l[f'{atr}_sugerido'] for l in linhas)))
    mot = Counter(m for l in linhas for m in l["motivos_revisao"].split(";") if m)
    print("Motivos de revisão:", dict(mot))
    print(f"Imagens para revisar: {len(rev)} de {len(linhas)} (auditoria cega: {mot['auditoria']}). Nada no dataset foi alterado.")


if __name__ == "__main__":
    main()
