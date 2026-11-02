#!/usr/bin/env python3
"""
Etapa 1 - Identificação da origem do dataset (SOMENTE LEITURA).

Baixa (ou lê de um caminho local) o dataset e registra a proveniência:
  relatorios/01_origem/origem.json          -> referência, URL, versão, data, ambiente
  relatorios/01_origem/manifesto_sha256.csv -> hash de TODOS os arquivos (prova de integridade)
  relatorios/01_origem/estrutura.csv        -> arquivos por subpasta e extensão

Uso:
  python scripts/01_origem.py                      # baixa via kagglehub
  python scripts/01_origem.py --path /pasta/local  # usa cópia já baixada
"""
import argparse, csv, hashlib, json, platform, re, sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REF = "phylake1337/fire-dataset"
URL = f"https://www.kaggle.com/datasets/{REF}"


def sha256(p, bloco=1 << 20):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while c := f.read(bloco):
            h.update(c)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", help="pasta já baixada (evita novo download)")
    ap.add_argument("--saida", default="relatorios/01_origem")
    a = ap.parse_args()

    versao_kagglehub = ""
    if a.path:
        raiz = Path(a.path).expanduser().resolve()
    else:
        import kagglehub
        versao_kagglehub = getattr(kagglehub, "__version__", "")
        raiz = Path(kagglehub.dataset_download(REF)).resolve()
    if not raiz.is_dir():
        sys.exit(f"Pasta não encontrada: {raiz}")

    m = re.search(r"versions[/\\](\d+)", str(raiz))
    saida = Path(a.saida)
    saida.mkdir(parents=True, exist_ok=True)

    arquivos = sorted(p for p in raiz.rglob("*") if p.is_file())
    manifesto, estrutura, total = [], Counter(), 0
    for p in arquivos:
        rel = p.relative_to(raiz)
        tam = p.stat().st_size
        total += tam
        manifesto.append({"caminho_relativo": str(rel), "tamanho_bytes": tam, "sha256": sha256(p)})
        estrutura[(str(rel.parent), p.suffix.lower())] += 1

    with open(saida / "manifesto_sha256.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["caminho_relativo", "tamanho_bytes", "sha256"])
        w.writeheader(); w.writerows(manifesto)
    with open(saida / "estrutura.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["subpasta", "extensao", "arquivos"])
        for (d, e), q in sorted(estrutura.items()):
            w.writerow([d, e, q])

    origem = {
        "dataset_ref": REF,
        "url": URL,
        "versao_kaggle": int(m.group(1)) if m else None,
        "data_download_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "caminho_local": str(raiz),
        "total_arquivos": len(arquivos),
        "tamanho_total_bytes": total,
        "python": platform.python_version(),
        "kagglehub": versao_kagglehub,
        # Campos que NÃO dá para obter offline: preencher manualmente na página do Kaggle
        "licenca": "PREENCHER (ver página do dataset)",
        "autor_citacao": "PREENCHER",
        "descricao_oficial_classes": "PREENCHER (copiar da página; conferir depois com as imagens)",
        "observacoes": "",
    }
    # Preserva o que foi preenchido à mão (licença, autores, descrição, observações e qualquer campo extra).
    destino = saida / "origem.json"
    if destino.exists():
        anterior = json.loads(destino.read_text(encoding="utf-8"))
        automaticos = {"dataset_ref", "url", "versao_kaggle", "data_download_utc", "caminho_local",
                       "total_arquivos", "tamanho_total_bytes", "python", "kagglehub"}
        mantidos = []
        for k, v in anterior.items():
            if k not in automaticos and v and not str(v).startswith("PREENCHER"):
                origem[k] = v; mantidos.append(k)
        for k in ("total_arquivos", "tamanho_total_bytes"):
            if k in anterior and anterior[k] != origem[k]:
                print(f"ATENÇÃO: {k} mudou de {anterior[k]} para {origem[k]} (o dataset local mudou?)")
        if mantidos:
            print("Campos preenchidos à mão mantidos:", ", ".join(mantidos))
    destino.write_text(json.dumps(origem, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(origem, indent=2, ensure_ascii=False))
    print(f"\nRelatórios em: {saida.resolve()}  | nada foi alterado no dataset.")


if __name__ == "__main__":
    main()
