#!/usr/bin/env python3
"""
Etapa 6 - INVENTÁRIO e PLANO DE ORGANIZAÇÃO (SOMENTE LEITURA: nada é copiado aqui).

Junta tudo o que as etapas anteriores decidiram e diz, imagem por imagem, para onde ela vai na cópia
organizada. A cópia de verdade só acontece na Etapa 7, DEPOIS da aprovação deste plano.

Estrutura planejada (o split NÃO vira pasta; fica no inventário):
  data/dataset_organizado/<ambiente>/com_fogo|sem_fogo|revisar/<nome_novo>
  data/dataset_organizado/_fora_da_divisao/<motivo>/<nome_novo>     (não fotografia, GIF animado, ...)

Nome novo: <prefixo>__<nome original sem extensão><extensão do formato REAL> (ex.: fire-dataset__fire.100.jpg).
A cópia será byte a byte (sem recodificar); só a extensão passa a dizer a verdade sobre o formato.

Entradas : 01_origem/origem.json e manifesto_sha256.csv, 02_validacao/validacao.csv,
           05_consolidacao/rotulos.csv, 04_divisao/divisao.csv e pendentes.csv
Saídas   : relatorios/06_plano/
  inventario.csv          -> uma linha por arquivo do dataset, com rótulos, fontes, split, situação e destino
  plano_organizacao.csv   -> só o que será copiado: origem, destino, tamanho e SHA-256 esperado
  resumo_plano.txt        -> contagens por pasta de destino e por split (para aprovar)

Uso:  python scripts/06_plano.py [--prefixo fire-dataset]
"""
import argparse, csv, json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath

EXT = {"JPEG": ".jpg", "MPO": ".jpg", "PNG": ".png", "GIF": ".gif", "BMP": ".bmp", "TIFF": ".tif", "WEBP": ".webp"}
PASTA_FOGO = {"sim": "com_fogo", "nao": "sem_fogo", "incerto": "revisar"}


def ler(caminho):
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def gravar(caminho, linhas, cols):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(linhas)


def nome_base(caminho_relativo):
    return PureWindowsPath(caminho_relativo.replace("/", "\\")).name   # funciona com \ e com /


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--origem", default="relatorios/01_origem/origem.json")
    ap.add_argument("--manifesto", default="relatorios/01_origem/manifesto_sha256.csv")
    ap.add_argument("--validacao", default="relatorios/02_validacao/validacao.csv")
    ap.add_argument("--rotulos", default="relatorios/05_consolidacao/rotulos.csv")
    ap.add_argument("--divisao", default="relatorios/04_divisao/divisao.csv")
    ap.add_argument("--pendentes", default="relatorios/04_divisao/pendentes.csv")
    ap.add_argument("--destino", default="data/dataset_organizado")
    ap.add_argument("--prefixo", default="fire-dataset", help="identifica o dataset no nome novo (evita colisão entre datasets)")
    ap.add_argument("--saida", default="relatorios/06_plano")
    a = ap.parse_args()

    origem = json.loads(Path(a.origem).read_text(encoding="utf-8"))
    man = {r["caminho_relativo"]: r for r in ler(a.manifesto)}
    val = {r["caminho_relativo"]: r for r in ler(a.validacao)}
    rot = {r["caminho_relativo"]: r for r in ler(a.rotulos)}
    div = {r["caminho_relativo"]: r for r in ler(a.divisao)}
    pend = {r["caminho_relativo"]: r for r in ler(a.pendentes)}

    erros = []
    for nome, d in (("validacao", val), ("rotulos", rot)):
        falta = sorted(set(man) - set(d))
        if falta: erros.append(f"{len(falta)} arquivos do manifesto sem linha em {nome} (ex.: {falta[0]})")
    sem_destino = sorted(k for k in rot if k not in div and k not in pend)
    if sem_destino: erros.append(f"{len(sem_destino)} imagens nem divididas nem pendentes (ex.: {sem_destino[0]})")
    if erros:
        raise SystemExit("Entradas inconsistentes:\n  " + "\n  ".join(erros))

    inv, plano = [], []
    for k in sorted(man):
        m, v, r = man[k], val[k], rot[k]
        fmt = v["formato_real"]
        ext = EXT.get(fmt)
        nome_novo = f"{a.prefixo}__{Path(nome_base(k)).stem}{ext}" if ext else ""
        if k in div:
            situacao, motivo, split = "incluida", "", div[k]["split"]
            pasta = f"{r['ambiente']}/{'revisar' if r['ambiente'] == 'ambiente_incerto' else PASTA_FOGO[r['fogo']]}"
        else:
            p = pend[k]; split = ""
            if r["tipo_imagem"] in ("sintetica", "visualizacao_sensor"):
                situacao, motivo, pasta = "fora_da_divisao", f"nao_fotografia ({r['tipo_imagem']})", f"_fora_da_divisao/{r['tipo_imagem']}"
            elif "GIF animado" in p["motivo"]:
                situacao, motivo, pasta = "fora_da_divisao", p["motivo"], "_fora_da_divisao/gif_animado"
            else:
                situacao, motivo, pasta = "fora_da_divisao", p["motivo"], "_fora_da_divisao/outros"
        if not ext:
            erros.append(f"formato sem extensão conhecida: {fmt} ({k})")
        destino = f"{a.destino}/{pasta}/{nome_novo}"
        inv.append({
            "dataset": origem.get("dataset_ref", ""), "versao": origem.get("versao_kaggle", ""),
            "caminho_original": k, "classe_original": r["classe_original"], "sha256": m["sha256"],
            "tamanho_bytes": m["tamanho_bytes"], "formato_real": fmt, "extensao_original": Path(nome_base(k)).suffix,
            "largura": v["largura"], "altura": v["altura"],
            "ambiente": r["ambiente"], "fonte_ambiente": r["fonte_ambiente"], "fogo": r["fogo"], "fonte_fogo": r["fonte_fogo"],
            "fumaca": r["fumaca"], "fonte_fumaca": r["fonte_fumaca"], "tipo_imagem": r["tipo_imagem"], "fonte_tipo": r["fonte_tipo"],
            "camera": r["camera"], "camera_sugerida_fraca": r["camera_sugerida_fraca"], "situacao_revisao": r["situacao"],
            "pasta_diverge_do_fogo": r["pasta_diverge_do_fogo"], "id_grupo": r["id_grupo"],
            "unidade_divisao": div.get(k, {}).get("unidade_divisao", ""), "split": split,
            "situacao": situacao, "motivo": motivo, "justificativa": r.get("justificativa_decisao", ""),
            "observacao": r.get("observacao", ""), "nome_novo": nome_novo, "destino": destino})
        plano.append({"caminho_original": k, "destino": destino, "tamanho_bytes": m["tamanho_bytes"],
                      "sha256": m["sha256"], "operacao": "copiar_bytes"})

    dup = [d for d, q in Counter(p["destino"] for p in plano).items() if q > 1]
    if dup: erros.append(f"{len(dup)} destinos repetidos (ex.: {dup[0]})")
    if erros:
        raise SystemExit("Plano inválido:\n  " + "\n  ".join(erros))

    saida = Path(a.saida); saida.mkdir(parents=True, exist_ok=True)
    gravar(saida / "inventario.csv", inv, list(inv[0].keys()))
    gravar(saida / "plano_organizacao.csv", plano, list(plano[0].keys()))

    pasta_de = lambda d: d[len(a.destino) + 1:].rsplit("/", 1)[0]
    por_pasta = Counter(pasta_de(i["destino"]) for i in inv)
    por_split = Counter((i["split"] or "-", i["fogo"]) for i in inv if i["situacao"] == "incluida")
    total_bytes = sum(int(i["tamanho_bytes"]) for i in inv)
    renomeia_ext = sum(i["extensao_original"].lower() != Path(i["nome_novo"]).suffix for i in inv)
    txt = [f"Plano gerado em {datetime.now(timezone.utc).isoformat(timespec='seconds')} | NADA FOI COPIADO",
           f"dataset: {origem.get('dataset_ref')} v{origem.get('versao_kaggle')} | arquivos: {len(inv)} | "
           f"{total_bytes / 1e6:.1f} MB | destino: {a.destino}/",
           f"situação: {dict(Counter(i['situacao'] for i in inv))}",
           f"extensão corrigida (ex.: .png que é JPEG -> .jpg): {renomeia_ext} arquivos | formato real: {dict(Counter(i['formato_real'] for i in inv))}",
           "", "Pastas de destino:"]
    txt += [f"  {p:40s} {q:4d}" for p, q in sorted(por_pasta.items())]
    txt += ["", "Divisão (só as incluídas): split x fogo"]
    for s in ("treino", "validacao", "teste"):
        txt.append(f"  {s:10s} com fogo {por_split[(s, 'sim')]:4d} | sem fogo {por_split[(s, 'nao')]:4d}")
    txt += ["", "Origem dos rótulos (todas as imagens):",
            f"  ambiente: {dict(Counter(i['fonte_ambiente'] for i in inv))}",
            f"  fogo    : {dict(Counter(i['fonte_fogo'] for i in inv))}",
            "", "Fora da divisão:"]
    txt += [f"  {i['caminho_original']}: {i['motivo']}" for i in inv if i["situacao"] != "incluida"]
    (saida / "resumo_plano.txt").write_text("\n".join(txt) + "\n", encoding="utf-8")
    print("\n".join(txt))
    print(f"\nInventário e plano em {saida}. NADA foi copiado: revise o plano antes da Etapa 7.")


if __name__ == "__main__":
    main()
