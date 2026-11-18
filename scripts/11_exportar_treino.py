#!/usr/bin/env python3
"""
Etapa 11 - EXPORTAR PARA O TREINO (cópia; nada do dataset organizado é alterado).

Monta a pasta que o repositório de treino (RD_Ignisalert) espera:

    <saida>/train|val|test/Fire|NoFire/<nome_novo>
    <saida>/split_manifest.csv      (mesmo formato do prepare_dataset do RD; o train.py confere cada SHA-256)
    <saida>/dataset_summary.json    (contagens por split e classe)
    <saida>/estratos.csv            (ambiente e fonte de cada imagem, para medir o erro por condição depois)

Regras:
  * só entram imagens com situacao = incluida no inventário (fora_da_divisao fica de fora e é listada);
  * a classe vem da coluna fogo da revisão (sim -> Fire, nao -> NoFire), nunca do nome da pasta de origem;
    fumaça sem chama visível é NoFire;
  * o split é o congelado no inventário (treino/validacao/teste) e o grupo de duplicatas vai como group_key,
    então o verify_manifest do RD recusa o treino se algum grupo aparecer em dois splits;
  * os bytes são copiados sem recodificar; o SHA-256 da cópia é conferido contra o arquivo de origem.

Entrada : data/dataset_organizado/inventario.csv
Saída   : data/treino_ignis/ (padrão; fora do git)

Uso:  python scripts/11_exportar_treino.py [--saida data/treino_ignis] [--sobrescrever]
"""
import argparse, csv, hashlib, json, shutil, sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parent.parent
SPLIT = {"treino": "train", "validacao": "val", "teste": "test"}
CLASSE = {"sim": "Fire", "nao": "NoFire"}
CAMPOS = ["label", "source_id", "original_path", "filename", "sha256", "dhash",
          "width", "height", "mode", "group_key", "split", "path"]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def dhash(img: Image.Image) -> str:
    g = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    px = g.tobytes()
    bits = 0
    for lin in range(8):
        for col in range(8):
            bits = (bits << 1) | (px[lin * 9 + col] > px[lin * 9 + col + 1])
    return f"{bits:016x}"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--inventario", default="data/dataset_organizado/inventario.csv")
    ap.add_argument("--saida", default="data/treino_ignis")
    ap.add_argument("--sobrescrever", action="store_true")
    a = ap.parse_args()

    inv = RAIZ / a.inventario
    saida = RAIZ / a.saida
    if saida.exists():
        if not a.sobrescrever:
            sys.exit(f"[PARADO] {saida} já existe. Use --sobrescrever para refazer (apaga só essa pasta de exportação).")
        if not (saida / "split_manifest.csv").is_file():
            sys.exit(f"[PARADO] {saida} existe mas não parece uma exportação desta etapa; não vou apagar.")
        shutil.rmtree(saida)

    linhas = list(csv.DictReader(inv.open(encoding="utf-8")))
    manifesto, estratos, fora = [], [], []
    for l in linhas:
        if l["situacao"] != "incluida":
            fora.append((l["nome_novo"] or l["caminho_original"], l["situacao"], l["motivo"]))
            continue
        if l["split"] not in SPLIT or l["fogo"] not in CLASSE:
            sys.exit(f"[ERRO] split/fogo inesperado em {l['nome_novo']}: {l['split']!r} {l['fogo']!r}")
        origem = RAIZ / l["destino"]
        split, classe = SPLIT[l["split"]], CLASSE[l["fogo"]]
        rel = Path(split) / classe / l["nome_novo"]
        destino = saida / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origem, destino)
        h = sha256(destino)
        if h != sha256(origem):
            sys.exit(f"[ERRO] cópia divergente: {origem}")
        with Image.open(destino) as im:
            w, hgt, modo, dh = im.width, im.height, im.mode, dhash(im)
        manifesto.append({
            "label": classe, "source_id": l["dataset"].split("/")[-1],
            "original_path": l["caminho_original"], "filename": l["nome_novo"],
            "sha256": h, "dhash": dh, "width": w, "height": hgt, "mode": modo,
            "group_key": l["unidade_divisao"], "split": split, "path": rel.as_posix(),
        })
        estratos.append({"path": rel.as_posix(), "split": split, "label": classe,
                         "ambiente": l["ambiente"], "fonte": l["dataset"].split("/")[-1],
                         "fumaca": l["fumaca"], "group_key": l["unidade_divisao"]})

    # mesma checagem do RD: nenhum grupo e nenhum SHA em dois splits
    por_grupo, por_sha = {}, {}
    for m in manifesto:
        por_grupo.setdefault(m["group_key"], set()).add(m["split"])
        por_sha.setdefault(m["sha256"], set()).add(m["split"])
    vaz = [g for g, s in por_grupo.items() if len(s) > 1] + [x for x, s in por_sha.items() if len(s) > 1]
    if vaz:
        sys.exit(f"[ERRO] grupo ou duplicata exata em mais de um split: {vaz[:5]}")

    with (saida / "split_manifest.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS); w.writeheader(); w.writerows(manifesto)
    with (saida / "estratos.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(estratos[0])); w.writeheader(); w.writerows(estratos)
    with (saida / "fora_do_treino.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["imagem", "situacao", "motivo"]); w.writerows(fora)
    cont = Counter((m["split"], m["label"]) for m in manifesto)
    resumo = {
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "inventario": a.inventario, "inventario_sha256": sha256(inv),
        "imagens": len(manifesto), "fora_do_treino": len(fora),
        "counts": {f"{s}/{c}": n for (s, c), n in sorted(cont.items())},
    }
    (saida / "dataset_summary.json").write_text(json.dumps(resumo, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[OK] {len(manifesto)} imagens copiadas para {saida} | {len(fora)} fora (lista em fora_do_treino.csv)")
    for s in ("train", "val", "test"):
        print(f"  {s:5s}  Fire {cont[(s, 'Fire')]:4d}   NoFire {cont[(s, 'NoFire')]:4d}")


if __name__ == "__main__":
    main()
