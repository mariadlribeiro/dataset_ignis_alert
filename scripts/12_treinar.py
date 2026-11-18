#!/usr/bin/env python3
"""
Etapa 12 - TREINO E AVALIAÇÃO Fire/NoFire (lê a cópia da etapa 11; nenhuma imagem é alterada).

Protocolo (o mesmo para as três redes, para a comparação ser justa):
  * rede pré-treinada no ImageNet (resnet18, densenet121 ou efficientnet_b0), última camada trocada por 2 saídas;
  * aumento de dados só no treino, na memória: recorte aleatório, espelho, rotação de até 12 graus e variação de
    brilho/contraste/saturação. Validação e teste: redimensiona o menor lado para 256 e recorta o centro 224x224
    (a imagem nunca é achatada, então o formato quadrado/paisagem pesa menos);
  * perda com peso por classe (as duas classes valem o mesmo), AdamW, lr 1e-4;
  * a cada época mede a validação; guarda a época com maior F2 de fogo (F2 dá mais peso a não perder fogo);
    para se a validação não melhorar por --paciencia épocas;
  * o limiar de decisão é calibrado SÓ na validação (maior F2); o teste é usado uma única vez, no fim;
  * o teste é quebrado por condição (ambiente, fonte, iluminação, formato, tamanho) para ver se o modelo
    acerta pelo motivo certo ou por atalho.

Entrada : data/treino_ignis/ (etapa 11) e relatorios/09_condicoes/combinado_1388/medidas_auto.csv
Saídas  : relatorios/12_treino/<nome>/   (métricas, predições, histórico, condições, resumo.txt, gráficos)
          data/modelos/<nome>/modelo.pth (pesos; fora do git)

Uso:
  python scripts/12_treinar.py --rede resnet18 --teste-rapido     (1 época, poucas imagens: só confere se roda)
  python scripts/12_treinar.py --rede resnet18
  python scripts/12_treinar.py --rede densenet121
  python scripts/12_treinar.py --rede efficientnet_b0
Requer: torch e torchvision (pip install torchvision)
"""
import argparse, csv, hashlib, json, math, random, sys, time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision import models, transforms

RAIZ = Path(__file__).resolve().parent.parent
MEDIA, DESVIO = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]
REDES = ("resnet18", "densenet121", "efficientnet_b0")


# ------------------------------------------------------------------ dados
def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def ler_manifesto(pasta: Path, conferir_sha: bool):
    linhas = list(csv.DictReader((pasta / "split_manifest.csv").open(encoding="utf-8")))
    grupos = defaultdict(set)
    for l in linhas:
        p = pasta / l["path"]
        if not p.is_file():
            sys.exit(f"[ERRO] imagem do manifesto ausente: {p}")
        if conferir_sha and sha256(p) != l["sha256"]:
            sys.exit(f"[ERRO] SHA-256 diferente do manifesto: {p}")
        grupos[l["group_key"]].add(l["split"])
    vaz = [g for g, s in grupos.items() if len(s) > 1]
    if vaz:
        sys.exit(f"[ERRO] grupos em mais de um split: {vaz[:5]}")
    return linhas


class Imagens(Dataset):
    def __init__(self, pasta, linhas, transform):
        self.pasta, self.linhas, self.t = pasta, linhas, transform

    def __len__(self):
        return len(self.linhas)

    def __getitem__(self, i):
        l = self.linhas[i]
        with Image.open(self.pasta / l["path"]) as im:
            x = self.t(im.convert("RGB"))
        return x, int(l["label"] == "Fire"), i


def transformacoes(tam, aumento):
    aval = transforms.Compose([transforms.Resize(round(tam * 256 / 224)), transforms.CenterCrop(tam),
                               transforms.ToTensor(), transforms.Normalize(MEDIA, DESVIO)])
    if aumento == "nenhum":
        return aval, aval
    treino = transforms.Compose([
        transforms.RandomResizedCrop(tam, scale=(0.80, 1.0)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(12),
        transforms.ColorJitter(brightness=0.25, contrast=0.25, saturation=0.15),
        transforms.ToTensor(), transforms.Normalize(MEDIA, DESVIO)])
    return treino, aval


# ------------------------------------------------------------------ modelo
def criar_rede(nome, pre_treinada=True):
    if nome == "resnet18":
        m = models.resnet18(weights=models.ResNet18_Weights.DEFAULT if pre_treinada else None)
        m.fc = nn.Linear(m.fc.in_features, 2)
    elif nome == "densenet121":
        m = models.densenet121(weights=models.DenseNet121_Weights.DEFAULT if pre_treinada else None)
        m.classifier = nn.Linear(m.classifier.in_features, 2)
    elif nome == "efficientnet_b0":
        m = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.DEFAULT if pre_treinada else None)
        m.classifier[1] = nn.Linear(m.classifier[1].in_features, 2)
    else:
        raise ValueError(nome)
    return m


# ------------------------------------------------------------------ métricas (fogo = classe positiva)
def metricas(y, p, limiar):
    y = np.asarray(y); prev = (np.asarray(p) >= limiar).astype(int)
    vp = int(((prev == 1) & (y == 1)).sum()); vn = int(((prev == 0) & (y == 0)).sum())
    fp = int(((prev == 1) & (y == 0)).sum()); fn = int(((prev == 0) & (y == 1)).sum())
    prec = vp / (vp + fp) if vp + fp else 0.0
    rec = vp / (vp + fn) if vp + fn else 0.0
    f2 = 5 * prec * rec / (4 * prec + rec) if prec + rec else 0.0
    return {"limiar": round(float(limiar), 4), "precisao_fogo": prec, "recall_fogo": rec, "f2_fogo": f2,
            "taxa_falso_negativo": fn / (vp + fn) if vp + fn else 0.0,
            "especificidade": vn / (vn + fp) if vn + fp else 0.0,
            "acuracia": (vp + vn) / len(y) if len(y) else 0.0,
            "vp": vp, "vn": vn, "fp": fp, "fn": fn}


def auc_roc(y, p):
    y = np.asarray(y); p = np.asarray(p)
    pos, neg = p[y == 1], p[y == 0]
    if not len(pos) or not len(neg):
        return float("nan")
    ordem = np.argsort(np.concatenate([pos, neg]), kind="mergesort")
    postos = np.empty(len(ordem)); postos[ordem] = np.arange(1, len(ordem) + 1)
    todos = np.concatenate([pos, neg])          # empates recebem o posto médio
    for v in np.unique(todos):
        idx = todos == v
        if idx.sum() > 1:
            postos[idx] = postos[idx].mean()
    return float((postos[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def calibrar_limiar(y, p):
    melhor = metricas(y, p, 0.5)
    for t in np.unique(np.round(p, 4)):
        m = metricas(y, p, t)
        if m["f2_fogo"] > melhor["f2_fogo"] + 1e-12:
            melhor = m
    return melhor["limiar"]


@torch.no_grad()
def prever(rede, carregador, disp):
    rede.eval(); probs, ys, idx, perda, n = [], [], [], 0.0, 0
    for x, y, i in carregador:
        out = rede(x.to(disp))
        perda += nn.functional.cross_entropy(out, y.to(disp), reduction="sum").item(); n += len(y)
        probs += torch.softmax(out, 1)[:, 1].cpu().tolist(); ys += y.tolist(); idx += i.tolist()
    return np.array(ys), np.array(probs), idx, perda / max(n, 1)


# ------------------------------------------------------------------ condições
def condicoes(linha, med):
    c = {"ambiente": linha.get("ambiente", ""), "fonte": linha["source_id"]}
    m = med.get(linha["sha256"])
    if m:
        c["iluminacao"] = m["iluminacao"]
        c["formato"] = "quadrada" if m["orientacao"] == "quadrada" else "nao_quadrada"
        c["tamanho"] = "pequena (<300 px)" if min(int(m["largura"]), int(m["altura"])) < 300 else "300 px ou mais"
    return c


def por_condicao(linhas, ys, ps, limiar):
    grupos = defaultdict(list)
    for l, y, p in zip(linhas, ys, ps):
        for chave, valor in l["_cond"].items():
            grupos[(chave, valor)].append((y, p))
    saida = []
    for (chave, valor), v in sorted(grupos.items()):
        y = np.array([a for a, _ in v]); p = np.array([b for _, b in v])
        m = metricas(y, p, limiar)
        saida.append({"condicao": chave, "valor": valor, "imagens": len(y),
                      "com_fogo": int(y.sum()), "sem_fogo": int((1 - y).sum()),
                      "recall_fogo": round(m["recall_fogo"], 4) if y.sum() else "",
                      "especificidade": round(m["especificidade"], 4) if (1 - y).sum() else "",
                      "falsos_negativos": m["fn"], "falsos_positivos": m["fp"],
                      "aviso": "poucas imagens (<20): ler com cuidado" if len(y) < 20 else ""})
    return saida


# ------------------------------------------------------------------ principal
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--rede", choices=REDES, default="resnet18")
    ap.add_argument("--dados", default="data/treino_ignis")
    ap.add_argument("--nome", help="nome da execução (padrão: <rede>_<aumento>)")
    ap.add_argument("--aumento", choices=("torchvision", "nenhum"), default="torchvision")
    ap.add_argument("--epocas", type=int, default=20)
    ap.add_argument("--lote", type=int, default=8)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--paciencia", type=int, default=7)
    ap.add_argument("--tamanho", type=int, default=224)
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--semente", type=int, default=42)
    ap.add_argument("--sem-pre-treino", action="store_true")
    ap.add_argument("--teste-rapido", action="store_true", help="1 época e 40 imagens por split, só para conferir")
    ap.add_argument("--sobrescrever", action="store_true")
    a = ap.parse_args()

    random.seed(a.semente); np.random.seed(a.semente); torch.manual_seed(a.semente)
    disp = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    nome = a.nome or f"{a.rede}_{a.aumento}" + ("_rapido" if a.teste_rapido else "")
    rel = RAIZ / "relatorios" / "12_treino" / nome
    pesos_dir = RAIZ / "data" / "modelos" / nome
    if (rel / "metricas_teste.json").exists() and not a.sobrescrever:
        sys.exit(f"[PARADO] {rel} já tem resultado. Use --sobrescrever ou outro --nome.")
    rel.mkdir(parents=True, exist_ok=True); pesos_dir.mkdir(parents=True, exist_ok=True)

    pasta = RAIZ / a.dados
    print(f"Conferindo {pasta / 'split_manifest.csv'} (SHA-256 de cada imagem)...")
    linhas = ler_manifesto(pasta, conferir_sha=not a.teste_rapido)
    estr = {l["path"]: l for l in csv.DictReader((pasta / "estratos.csv").open(encoding="utf-8"))}
    arq_med = RAIZ / "relatorios/09_condicoes/combinado_1388/medidas_auto.csv"
    med = {m["sha256"]: m for m in csv.DictReader(arq_med.open(encoding="utf-8"))} if arq_med.exists() else {}
    for l in linhas:
        l["ambiente"] = estr.get(l["path"], {}).get("ambiente", "")
        l["_cond"] = condicoes(l, med)
    por = {s: [l for l in linhas if l["split"] == s] for s in ("train", "val", "test")}
    if a.teste_rapido:
        rnd = random.Random(a.semente)
        por = {s: rnd.sample(v, min(40, len(v))) for s, v in por.items()}
        a.epocas = 1

    t_treino, t_aval = transformacoes(a.tamanho, a.aumento)
    g = torch.Generator().manual_seed(a.semente)
    kw = dict(batch_size=a.lote, num_workers=a.workers)
    c_treino = DataLoader(Imagens(pasta, por["train"], t_treino), shuffle=True, generator=g, **kw)
    c_val = DataLoader(Imagens(pasta, por["val"], t_aval), shuffle=False, **kw)
    c_teste = DataLoader(Imagens(pasta, por["test"], t_aval), shuffle=False, **kw)
    n_fogo = sum(l["label"] == "Fire" for l in por["train"]); n_sem = len(por["train"]) - n_fogo
    peso_classe = torch.tensor([len(por["train"]) / (2 * n_sem), len(por["train"]) / (2 * n_fogo)],
                               dtype=torch.float32, device=disp)
    print(f"Rede {a.rede} | dispositivo {disp} | treino {len(por['train'])} (fogo {n_fogo}, sem fogo {n_sem}) "
          f"| validação {len(por['val'])} | teste {len(por['test'])}")

    rede = criar_rede(a.rede, not a.sem_pre_treino).to(disp)
    perda_fn = nn.CrossEntropyLoss(weight=peso_classe)
    otim = torch.optim.AdamW(rede.parameters(), lr=a.lr, weight_decay=1e-4)
    agenda = torch.optim.lr_scheduler.CosineAnnealingLR(otim, T_max=a.epocas)

    hist, melhor_f2, melhor_ep, sem_melhora = [], -1.0, 0, 0
    inicio = time.time()
    for ep in range(1, a.epocas + 1):
        t0 = time.time(); rede.train(); soma, n, certos = 0.0, 0, 0
        for x, y, _ in c_treino:
            x, y = x.to(disp), y.to(disp)
            otim.zero_grad(set_to_none=True)
            out = rede(x); perda = perda_fn(out, y); perda.backward(); otim.step()
            soma += perda.item() * len(y); n += len(y); certos += (out.argmax(1) == y).sum().item()
        agenda.step()
        yv, pv, _, perda_v = prever(rede, c_val, disp)
        mv = metricas(yv, pv, 0.5)
        hist.append({"epoca": ep, "perda_treino": round(soma / n, 4), "acuracia_treino": round(certos / n, 4),
                     "perda_val": round(perda_v, 4), "f2_val": round(mv["f2_fogo"], 4),
                     "recall_val": round(mv["recall_fogo"], 4), "especificidade_val": round(mv["especificidade"], 4),
                     "segundos": round(time.time() - t0, 1)})
        marca = ""
        if mv["f2_fogo"] > melhor_f2:
            melhor_f2, melhor_ep, sem_melhora, marca = mv["f2_fogo"], ep, 0, "  <- melhor até agora (salvo)"
            torch.save({"rede": a.rede, "estado": rede.state_dict(), "epoca": ep}, pesos_dir / "modelo.pth")
        else:
            sem_melhora += 1
        h = hist[-1]
        print(f"época {ep:2d}/{a.epocas} | perda treino {h['perda_treino']:.3f} | val: F2 {h['f2_val']:.3f} "
              f"recall {h['recall_val']:.3f} espec. {h['especificidade_val']:.3f} | {h['segundos']:.0f}s{marca}")
        if sem_melhora >= a.paciencia:
            print(f"Parada antecipada: {a.paciencia} épocas sem melhorar na validação.")
            break

    with (rel / "historico.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(hist[0])); w.writeheader(); w.writerows(hist)

    # melhor época -> limiar na validação -> teste uma única vez
    rede.load_state_dict(torch.load(pesos_dir / "modelo.pth", map_location=disp)["estado"])
    yv, pv, iv, _ = prever(rede, c_val, disp)
    limiar = calibrar_limiar(yv, pv)
    yt, pt, it, _ = prever(rede, c_teste, disp)
    res = {}
    for nome_s, y, p, idx, lst in (("validacao", yv, pv, iv, por["val"]), ("teste", yt, pt, it, por["test"])):
        m = metricas(y, p, limiar); m["auc_roc"] = auc_roc(y, p); m["imagens"] = len(y)
        res[nome_s] = m
        json.dump(m, (rel / f"metricas_{nome_s}.json").open("w", encoding="utf-8"), indent=2, ensure_ascii=False)
        ordem = [lst[k] for k in idx]
        with (rel / f"predicoes_{nome_s}.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["path", "classe_real", "prob_fogo", "previsto", "acertou", "erro",
                        "ambiente", "fonte", "iluminacao", "formato", "tamanho"])
            for l, yy, pp in zip(ordem, y, p):
                prev = int(pp >= limiar)
                erro = "" if prev == yy else ("falso_negativo" if yy == 1 else "falso_positivo")
                c = l["_cond"]
                w.writerow([l["path"], l["label"], round(float(pp), 4), "Fire" if prev else "NoFire",
                            "sim" if not erro else "nao", erro, c.get("ambiente", ""), c.get("fonte", ""),
                            c.get("iluminacao", ""), c.get("formato", ""), c.get("tamanho", "")])
        cond = por_condicao(ordem, y, p, limiar)
        with (rel / f"por_condicao_{nome_s}.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(cond[0])); w.writeheader(); w.writerows(cond)

    config = {**vars(a), "nome": nome, "dispositivo": str(disp), "melhor_epoca": melhor_ep,
              "epocas_rodadas": len(hist), "limiar_calibrado_na_validacao": limiar,
              "torch": torch.__version__, "manifesto_sha256": sha256(pasta / "split_manifest.csv"),
              "concluido_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "minutos": round((time.time() - inicio) / 60, 1)}
    json.dump(config, (rel / "config.json").open("w", encoding="utf-8"), indent=2, ensure_ascii=False)

    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
        e = [h["epoca"] for h in hist]
        ax[0].plot(e, [h["perda_treino"] for h in hist], label="treino"); ax[0].plot(e, [h["perda_val"] for h in hist], label="validação")
        ax[0].set_title("Perda"); ax[0].set_xlabel("época"); ax[0].legend()
        ax[1].plot(e, [h["f2_val"] for h in hist], label="F2"); ax[1].plot(e, [h["recall_val"] for h in hist], label="recall")
        ax[1].plot(e, [h["especificidade_val"] for h in hist], label="especificidade")
        ax[1].set_title("Validação (limiar 0,5)"); ax[1].set_xlabel("época"); ax[1].set_ylim(0, 1.02); ax[1].legend()
        fig.tight_layout(); fig.savefig(rel / "curvas.png", dpi=120); plt.close(fig)
    except Exception as erro:
        print("(gráfico não gerado:", erro, ")")

    t = res["teste"]
    linhas_res = [
        f"Etapa 12 | {nome} | {config['concluido_em']} | {config['minutos']} min em {disp}",
        f"melhor época {melhor_ep} de {len(hist)} | limiar calibrado na validação: {limiar}",
        "",
        f"TESTE ({t['imagens']} imagens, usado uma única vez)",
        f"  recall de fogo {t['recall_fogo']:.3f} | precisão {t['precisao_fogo']:.3f} | F2 {t['f2_fogo']:.3f} | "
        f"especificidade {t['especificidade']:.3f} | AUC {t['auc_roc']:.3f}",
        f"  fogo perdido (falso negativo): {t['fn']} | alarme falso (falso positivo): {t['fp']}",
        "",
        "Por condição no teste (recall = fogo encontrado; especificidade = sem fogo reconhecido):",
    ]
    for c in csv.DictReader((rel / "por_condicao_teste.csv").open(encoding="utf-8")):
        linhas_res.append(f"  {c['condicao']:10s} {c['valor']:18s} n={c['imagens']:>3}  recall {c['recall_fogo'] or '-':>6}  "
                          f"espec. {c['especificidade'] or '-':>6}  FN {c['falsos_negativos']} FP {c['falsos_positivos']}  {c['aviso']}")
    if a.teste_rapido:
        linhas_res.insert(1, "TESTE RÁPIDO: 1 época e 40 imagens por split. Números sem valor; só confere que o código roda.")
    (rel / "resumo.txt").write_text("\n".join(linhas_res) + "\n", encoding="utf-8")
    print("\n" + "\n".join(linhas_res))
    print(f"\n[OK] Relatórios em {rel}\n     Pesos em {pesos_dir / 'modelo.pth'} (fora do git)")


if __name__ == "__main__":
    main()
