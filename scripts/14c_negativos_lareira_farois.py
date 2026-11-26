#!/usr/bin/env python3
"""
Etapa 14c - NEGATIVOS DIFÍCEIS, 2ª RODADA: LAREIRA (chama controlada) E FARÓIS (nenhuma imagem é alterada).

A avaliação de 24/11/2026 listou lareira e faróis entre as cenas que enganam um detector de incêndio. A 1ª rodada
(14a/14b) não tinha os dois: a 2ª fonte é de floresta e quase não tem nenhum deles. Esta etapa aceita PASTAS DE
FORA, por exemplo fotos tiradas pela equipe com o celular ou imagens de licença livre (Pexels, Unsplash, Wikimedia),
e também procura na 2ª fonte o que houver.

Os dois tipos medem coisas diferentes, e o guia de rotulagem (GUIA_ROTULAGEM.md) explica por quê:
  * FARÓIS e lanternas de carro à noite: não há chama. Todo alarme é FALSO ALARME (como na 14b).
  * LAREIRA, vela, fogão, churrasco, fogueira controlada: HÁ chama, então pelo critério do projeto o rótulo de fogo
    é "sim". Não é incêndio. A rede foi treinada para achar chama, então aqui o alarme é esperado: a taxa mostra
    quanto a CONFIRMAÇÃO HUMANA do aplicativo é necessária, não um erro da rede.

Dois passos:
  1) selecionar: o CLIP escolhe as candidatas (lareira, faróis) nas pastas dadas; a página de revisão é cega
     (não mostra o tipo sugerido nem a pasta):
       python scripts/14c_negativos_lareira_farois.py selecionar --extra "C:\\Users\\maria\\Pictures\\negativos"
              [--nova "C:\\...\\forest-fire-image-dataset\\versions\\2"] [--por-tipo 40]
     Abra relatorios\\14_negativos\\rodada2\\revisao_rodada2.html, revise e exporte revisao_rodada2_preenchida.csv.
  2) avaliar: passa as imagens revisadas pelas redes da Etapa 12, com o limiar da validação:
       python scripts/14c_negativos_lareira_farois.py avaliar --revisao relatorios\\14_negativos\\rodada2\\revisao_rodada2_preenchida.csv

Privacidade: as imagens NÃO são copiadas para o repositório e NÃO vão para o treino. Fotos de celular têm GPS no
EXIF; a página só as mostra a partir do disco. Antes de publicar qualquer uma no site, use a Etapa 16.
Saídas: relatorios/14_negativos/rodada2/ (candidatos.csv, origem.json, resumo_selecao.txt, revisao_rodada2.html,
        resultado/resumo.txt, resultado/metricas.csv, resultado/predicoes_<rede>.csv)
"""
import argparse, csv, importlib.util, json, math, os, random, re, sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
REDES = ("resnet18", "efficientnet_b0", "densenet121")
EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
TIPOS2 = {
    "lareira": ["a photo of a fireplace with a fire", "a burning candle", "a gas stove flame", "a barbecue grill with flames",
                "a small campfire surrounded by stones", "a wood stove with fire inside"],
    "farois": ["car headlights at night", "a car with bright headlights on a dark road", "traffic at night with red tail lights",
               "a flashlight shining in the dark"],
}
NOME_TIPO = {"lareira": "Chama controlada (lareira, vela, fogão, churrasco)", "farois": "Faróis ou lanternas à noite",
             "nenhuma": "Outra cena"}


def m14a():
    spec = importlib.util.spec_from_file_location("sel14a", RAIZ / "scripts" / "14a_selecao_negativos.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    m.TIPOS = TIPOS2   # o CLIP da 14a passa a dar nota aos dois tipos novos (contra fogo, fumaça e cena comum)
    from PIL import Image
    m.abrir = lambda _raiz, caminho: Image.open(caminho)   # aqui cada candidata já vem com o caminho completo
    return m


def t12():
    spec = importlib.util.spec_from_file_location("treino12", RAIZ / "scripts" / "12_treinar.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def wilson(k, n, z=1.96):
    if n == 0: return float("nan"), float("nan")
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - m), min(1.0, c + m)


def taxa(k, n):
    if n == 0: return "      —"
    lo, hi = wilson(k, n)
    return f"{k:>3}/{n:<3} {100 * k / n:5.1f}% ({100 * lo:4.1f} a {100 * hi:4.1f})".replace(".", ",")


def caminho_real(origem, chave):
    rid, rel = chave.split("/", 1)
    return Path(origem[rid]) / Path(*rel.split("/"))


# ------------------------------------------------------------------ 1) selecionar
def selecionar(a):
    A = m14a(); sai = RAIZ / "relatorios/14_negativos/rodada2"; sai.mkdir(parents=True, exist_ok=True)
    raizes = {}
    for k, p in enumerate(a.extra or []):
        if not Path(p).is_dir(): sys.exit(f"[PARADO] pasta não existe: {p}")
        raizes[f"extra{k + 1}"] = str(Path(p).resolve())
    if a.nova:
        if not Path(a.nova).is_dir(): sys.exit(f"[PARADO] pasta não existe: {a.nova}")
        raizes["fonte2"] = str(Path(a.nova).resolve())
    if not raizes: sys.exit("[PARADO] dê ao menos uma pasta: --extra PASTA (fotos da equipe ou de licença livre) e/ou --nova.")

    # o que já foi usado (dataset, opção A, atalho, 1ª rodada) não entra de novo
    usadas = set()
    p10 = RAIZ / "relatorios/10_nova_fonte/cristiancristancho_forest-fire-image-dataset"
    for arq in [p10 / "selecao_A/revisao.csv", RAIZ / "relatorios/13_atalho/revisao.csv", RAIZ / "relatorios/14_negativos/candidatos.csv"]:
        if arq.exists(): usadas |= {r["caminho_relativo"].replace("\\", "/") for r in A.ler(arq)}
    man = A.ler(RAIZ / a.manifesto)
    dh_ds = np.array([int(m["dhash"], 16) for m in man], dtype=np.uint64)

    lista = []
    for rid, raiz in raizes.items():
        for p in sorted(Path(raiz).rglob("*")):
            if p.suffix.lower() in EXTS and p.is_file():
                rel = p.relative_to(raiz).as_posix()
                if rid == "fonte2" and rel in usadas: continue
                lista.append((rid, rel, p))
    print(f"Imagens nas pastas: {len(lista)}. Conferindo dHash contra o dataset...")
    ok, desc, prox, ruins = [], [], 0, 0
    from PIL import Image
    for k, (rid, rel, p) in enumerate(lista):
        try:
            with Image.open(p) as im: rgb = im.convert("RGB")
        except Exception:
            ruins += 1; continue
        d = int(min(bin(int(x)).count("1") for x in (dh_ds ^ np.uint64(A.dhash(rgb)))))
        if d <= a.dist_min: prox += 1; continue
        ok.append({"chave": f"{rid}/{rel}", "raiz": rid, "largura": rgb.width, "altura": rgb.height}); desc.append(A.descritor(rgb))
        if k % 200 == 0: print(f"  dHash {k}/{len(lista)}", end="\r")
    print(f"\n  quase iguais ao dataset: {prox} | ilegíveis: {ruins} | seguem: {len(ok)}")
    if not ok: sys.exit("[PARADO] nenhuma imagem utilizável.")

    cams = [str(caminho_real(raizes, r["chave"])) for r in ok]
    notas = A.notas_falsas(cams, a.semente) if a.teste_sem_modelo else A.notas_clip(None, cams, a.modelo)
    for r, s in zip(ok, notas):
        r["tipo_sugerido"] = max(TIPOS2, key=lambda t: s[t]); r["nota_tipo"] = round(s[r["tipo_sugerido"]], 4)
        r["nota_fogo"], r["nota_comum"] = round(s["fogo"], 4), round(s["comum"], 4)
    X = np.stack(desc); idx = {r["chave"]: k for k, r in enumerate(ok)}

    escolhidas, resumo = [], []
    for t in TIPOS2:
        # fotos de pastas EXTRA (escolhidas a dedo pela equipe) entram todas; da 2ª fonte, só as de maior nota
        grupo = [r for r in ok if r["tipo_sugerido"] == t]
        extra = [r for r in grupo if r["raiz"] != "fonte2"]
        f2 = sorted((r for r in grupo if r["raiz"] == "fonte2" and r["nota_tipo"] >= a.nota_min), key=lambda r: -r["nota_tipo"])[:a.pool]
        vagas = max(0, a.por_tipo - len(extra))
        esc = extra + ([f2[i] for i in A.k_centros(X[[idx[r["chave"]] for r in f2]], vagas)] if f2 and vagas else [])
        escolhidas += esc; resumo.append((t, len(grupo), len(extra), len(esc)))
    random.Random(a.semente).shuffle(escolhidas)
    for n, r in enumerate(escolhidas, 1): r["n"] = n
    A.gravar(sai / "candidatos.csv", escolhidas, ["n", "chave", "raiz", "tipo_sugerido", "nota_tipo", "nota_fogo", "nota_comum", "largura", "altura"])
    (sai / "origem.json").write_text(json.dumps(raizes, ensure_ascii=False, indent=2), encoding="utf-8")

    def uri(chave):
        txt = str(caminho_real(raizes, chave))
        return (PureWindowsPath if os.name != "nt" and re.match(r"^[A-Za-z]:[\\/]", txt) else Path)(txt).as_uri()
    dados = [{"n": r["n"], "caminho": r["chave"], "url": uri(r["chave"])} for r in escolhidas]
    pag = A.PAGINA
    antigo = pag[pag.index("  cena: {t:'Cena'"):pag.index("  fogo: {t:'Fogo'")]
    novo = ("  cena: {t:'Cena', crit:'O que pode ser confundido com um incêndio nesta foto (veja o GUIA_ROTULAGEM.md).',\n"
            "         ops:[['lareira','Chama controlada: lareira, vela, fogão, churrasco','1'],['farois','Faróis ou lanternas à noite','2'],"
            "['nenhuma','Outra cena','3']]},\n")
    html = (pag.replace(antigo, novo).replace("Teclas: 1 a 7", "Teclas: 1 a 3")
               .replace("Negativos difíceis · revisão cega", "Lareira e faróis · revisão cega")
               .replace("revisao_negativos_preenchida.csv", "revisao_rodada2_preenchida.csv")
               .replace("__DATA__", json.dumps(dados, ensure_ascii=False).replace("</", "<\\/"))
               .replace("__CHAVE__", json.dumps(f"ignis_negativos_rodada2_{a.semente}")))
    (sai / "revisao_rodada2.html").write_text(html, encoding="utf-8")
    txt = [f"Etapa 14c (seleção) | {datetime.now(timezone.utc).isoformat(timespec='seconds')} | "
           + ("NOTAS FALSAS (teste do script)" if a.teste_sem_modelo else a.modelo),
           "pastas: " + "; ".join(f"{k} = {v}" for k, v in raizes.items()),
           f"imagens: {len(lista)} | quase iguais ao dataset: {prox} | avaliadas: {len(ok)}", "",
           f"  {'tipo sugerido pelo CLIP':<52} {'com o tipo':>10} {'das pastas extra':>16} {'escolhidas':>11}"]
    txt += [f"  {NOME_TIPO[t]:<52} {n:>10} {e:>16} {s:>11}" for t, n, e, s in resumo]
    txt += ["", "Revisão: abra revisao_rodada2.html, marque cena, fogo e fumaça e exporte revisao_rodada2_preenchida.csv",
            "para relatorios/14_negativos/rodada2/. Depois: ... 14c_negativos_lareira_farois.py avaliar --revisao <csv>"]
    (sai / "resumo_selecao.txt").write_text("\n".join(txt) + "\n", encoding="utf-8")
    print("\n".join(txt))


# ------------------------------------------------------------------ 2) avaliar
def avaliar(a):
    sai = RAIZ / "relatorios/14_negativos/rodada2"; res_dir = sai / "resultado"; res_dir.mkdir(parents=True, exist_ok=True)
    if not Path(a.revisao).is_file(): sys.exit(f"[PARADO] Não achei {a.revisao}.")
    origem = json.loads((sai / "origem.json").read_text(encoding="utf-8"))
    cand = {r["chave"]: r for r in csv.DictReader((sai / "candidatos.csv").open(encoding="utf-8"))}
    itens, fora = [], []
    for r in csv.DictReader(open(a.revisao, encoding="utf-8-sig")):
        ch = r["caminho_relativo"]
        if ch not in cand: fora.append((ch, "não faz parte da seleção")); continue
        if r.get("revisado") != "sim": fora.append((ch, "sem revisão")); continue
        if r["fogo"] == "incerto": fora.append((ch, "fogo incerto")); continue
        if r["cena"] == "lareira" and r["fogo"] == "sim": grupo = "chama_controlada"
        elif r["fogo"] == "nao" and r["cena"] in ("farois", "lareira"): grupo = "farois" if r["cena"] == "farois" else "lareira_apagada"
        elif r["fogo"] == "nao": grupo = "outra_sem_fogo"
        else: fora.append((ch, "fogo sim fora de chama controlada (incêndio?)")); continue
        itens.append({"chave": ch, "grupo": grupo, "cena": r["cena"], "obs": r.get("observacao", "")})
    if not itens: sys.exit("[ERRO] nenhuma imagem revisada aproveitável.")

    if a.teste_sem_modelo:
        rng = np.random.default_rng(0); probs = {r: (rng.random(len(itens)), 0.5) for r in a.redes}
    else:
        import torch
        from PIL import Image
        T = t12(); _, aval = T.transformacoes(224, "nenhum"); X = []
        for i in itens:
            with Image.open(caminho_real(origem, i["chave"])) as im: X.append(aval(im.convert("RGB")))
        X = torch.stack(X); probs = {}
        for rede in a.redes:
            nome = f"{rede}_{a.sufixo}"; pesos = RAIZ / "data/modelos" / nome / "modelo.pth"; cfg = RAIZ / "relatorios/12_treino" / nome / "config.json"
            if not pesos.exists() or not cfg.exists(): print(f"[pulando] {nome}"); continue
            lim = json.loads(cfg.read_text(encoding="utf-8"))["limiar_calibrado_na_validacao"]
            m = T.criar_rede(rede, pre_treinada=False); m.load_state_dict(torch.load(pesos, map_location="cpu")["estado"]); m.eval()
            with torch.no_grad():
                p = np.concatenate([torch.softmax(m(X[k:k + 32]), 1)[:, 1].numpy() for k in range(0, len(X), 32)])
            probs[rede] = (p, lim)
    if not probs: sys.exit("[ERRO] nenhuma rede da Etapa 12 encontrada.")

    GR = [("farois", "Faróis ou lanternas à noite (FALSO ALARME)"), ("lareira_apagada", "Lareira ou fogão apagado (FALSO ALARME)"),
          ("outra_sem_fogo", "Outras cenas sem fogo (FALSO ALARME)"), ("chama_controlada", "Chama controlada (alarme esperado)")]
    cnt = Counter(i["grupo"] for i in itens)
    txt = [f"Etapa 14c (avaliação) | {datetime.now(timezone.utc).isoformat(timespec='seconds')}"
           + (" | TESTE SEM MODELO: números falsos" if a.teste_sem_modelo else ""),
           f"{len(itens)} imagens revisadas | fora: {len(fora)} (fora.csv)", "",
           "Taxa de ALARME por grupo (alarmes / imagens, intervalo de 95% de Wilson), limiar da validação:"]
    linhas = []
    for rede, (p, lim) in probs.items():
        al = p >= lim; txt += ["", f"{rede} (limiar {lim:.3f})"]; lin = {"rede": rede, "limiar": round(lim, 4)}
        for g, nome in GR:
            ix = [k for k, i in enumerate(itens) if i["grupo"] == g]; kk = int(sum(al[k] for k in ix))
            txt.append(f"  {nome:<46} {taxa(kk, len(ix))}"); lin[f"alarme_{g}"] = round(kk / len(ix), 4) if ix else ""; lin[f"n_{g}"] = len(ix)
        linhas.append(lin)
        with (res_dir / f"predicoes_{rede}.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n"); w.writerow(["chave", "grupo", "cena", "prob_fogo", "alarme", "observacao"])
            for k, i in enumerate(itens): w.writerow([i["chave"], i["grupo"], i["cena"], round(float(p[k]), 4), "sim" if al[k] else "", i["obs"]])
    with (res_dir / "metricas.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]), lineterminator="\n"); w.writeheader(); w.writerows(linhas)
    with (res_dir / "fora.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n"); w.writerow(["chave", "motivo"]); w.writerows(fora)
    txt += ["", "Leitura: nos faróis, todo alarme é falso e se soma aos da 14b. Na chama controlada, o alarme é o",
            "esperado de uma rede que acha chama: ela não sabe se o fogo está contido. Por isso o aplicativo pede",
            "confirmação humana; a taxa mostra quantas confirmações uma lareira ou um churrasco gerariam."]
    (res_dir / "resumo.txt").write_text("\n".join(txt) + "\n", encoding="utf-8")
    print("\n".join(txt)); print(f"\n[OK] {res_dir}")


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="passo", required=True)
    s = sub.add_parser("selecionar")
    s.add_argument("--extra", nargs="+", help="pastas com fotos da equipe ou de licença livre (lareira, vela, faróis...)")
    s.add_argument("--nova", help="pasta da 2ª fonte (procura lareira e faróis que houver)")
    s.add_argument("--por-tipo", type=int, default=40); s.add_argument("--pool", type=int, default=120)
    s.add_argument("--nota-min", type=float, default=0.30, help="nota mínima do CLIP para uma imagem da 2ª fonte entrar")
    s.add_argument("--dist-min", type=int, default=10); s.add_argument("--semente", type=int, default=42)
    s.add_argument("--modelo", default="openai/clip-vit-base-patch16")
    s.add_argument("--manifesto", default="data/treino_ignis/split_manifest.csv")
    s.add_argument("--teste-sem-modelo", action="store_true")
    v = sub.add_parser("avaliar")
    v.add_argument("--revisao", required=True); v.add_argument("--redes", nargs="+", default=list(REDES))
    v.add_argument("--sufixo", default="torchvision"); v.add_argument("--teste-sem-modelo", action="store_true")
    a = ap.parse_args()
    selecionar(a) if a.passo == "selecionar" else avaliar(a)


if __name__ == "__main__":
    main()
