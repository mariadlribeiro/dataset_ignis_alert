#!/usr/bin/env python3
"""
Etapa 7 - ORGANIZAÇÃO em CÓPIA, executando o plano aprovado (relatorios/06_plano/plano_organizacao.csv).

Garantias:
  * os ORIGINAIS nunca são modificados, movidos ou apagados (só lidos);
  * nada é sobrescrito nem apagado no destino: se o arquivo já existe com o mesmo SHA-256, é pulado
    (dá para rodar de novo com segurança); se existe com conteúdo DIFERENTE, o script para;
  * antes de copiar, o SHA-256 do original é conferido com o manifesto da Etapa 1;
  * a cópia é byte a byte (sem recodificar) para um arquivo temporário, que só recebe o nome final
    depois de o SHA-256 da cópia bater com o esperado.

Saídas:
  data/dataset_organizado/...                         -> as cópias, nas pastas do plano
  data/dataset_organizado/inventario.csv              -> cópia do inventário (a pasta se explica sozinha)
  relatorios/07_organizacao/log_operacoes.csv         -> uma linha por arquivo: o que foi feito e os hashes
  relatorios/07_organizacao/resumo_organizacao.txt    -> contagens e verificações finais

Uso:  python scripts/07_organizar.py --simular   # mostra o que faria, sem copiar nada
      python scripts/07_organizar.py             # executa
"""
import argparse, csv, hashlib, json, os, shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def ler(caminho):
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def sha256(p, bloco=1 << 20):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while c := f.read(bloco):
            h.update(c)
    return h.hexdigest()


def agora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--origem", default="relatorios/01_origem/origem.json")
    ap.add_argument("--plano", default="relatorios/06_plano/plano_organizacao.csv")
    ap.add_argument("--inventario", default="relatorios/06_plano/inventario.csv")
    ap.add_argument("--destino", default="data/dataset_organizado", help="pasta raiz da cópia (a mesma do 06_plano)")
    ap.add_argument("--saida", default="relatorios/07_organizacao")
    ap.add_argument("--simular", action="store_true", help="não copia nada; só verifica e mostra o que faria")
    a = ap.parse_args()

    raiz = Path(json.loads(Path(a.origem).read_text(encoding="utf-8"))["caminho_local"])
    plano = ler(a.plano)
    if not plano:
        raise SystemExit("Plano vazio.")
    destinos = [Path(p["destino"]) for p in plano]
    base = Path(a.destino)
    if len(set(destinos)) != len(destinos):
        raise SystemExit("O plano tem destinos repetidos. Gere o plano de novo (06_plano.py).")
    fora = [d for d in destinos if d.is_absolute() or ".." in d.parts or base not in d.parents]
    if fora:
        raise SystemExit(f"{len(fora)} destinos fora de {base}/ (ex.: {fora[0]}). Recusado.")

    # ---------- verificação prévia (nada é escrito aqui) ----------
    problemas, acoes = [], []
    for p in plano:
        src, dst = raiz / p["caminho_original"], Path(p["destino"])
        if not src.is_file():
            problemas.append(f"original não encontrado: {src}"); continue
        if src.stat().st_size != int(p["tamanho_bytes"]):
            problemas.append(f"tamanho do original mudou: {p['caminho_original']}"); continue
        if dst.exists():
            acoes.append((p, "ja_existe"))
        else:
            acoes.append((p, "copiar"))
    if problemas:
        raise SystemExit("Verificação prévia falhou (nada foi copiado):\n  " + "\n  ".join(problemas[:20]))
    extras = []
    if base.exists():
        planejados = {d.resolve() for d in destinos} | {(base / "inventario.csv").resolve()}
        extras = [q for q in base.rglob("*") if q.is_file() and q.resolve() not in planejados and not q.name.endswith(".tmp")]

    cont = Counter(x for _, x in acoes)
    print(f"Plano: {len(plano)} arquivos | destino: {base}/ | a copiar: {cont['copiar']} | já existentes: {cont['ja_existe']}")
    if extras:
        print(f"AVISO: {len(extras)} arquivos na pasta de destino que não estão no plano (não serão tocados), ex.: {extras[0]}")
    if a.simular:
        for p, x in acoes[:5]:
            print(f"  {x:9s} {p['caminho_original']} -> {p['destino']}")
        print("  ...\nSIMULAÇÃO: nada foi copiado. Rode sem --simular para executar.")
        return

    # ---------- execução ----------
    saida = Path(a.saida); saida.mkdir(parents=True, exist_ok=True)
    log, falhas = [], 0
    for i, (p, x) in enumerate(acoes, 1):
        src, dst = raiz / p["caminho_original"], Path(p["destino"])
        reg = {"caminho_original": p["caminho_original"], "destino": p["destino"], "tamanho_bytes": p["tamanho_bytes"],
               "sha256_esperado": p["sha256"], "sha256_origem": "", "sha256_copia": "", "status": "", "quando": agora()}
        try:
            h_src = sha256(src); reg["sha256_origem"] = h_src
            if h_src != p["sha256"]:
                reg["status"] = "erro_original_diferente_do_manifesto"; falhas += 1
            elif x == "ja_existe":
                h_dst = sha256(dst); reg["sha256_copia"] = h_dst
                if h_dst == p["sha256"]:
                    reg["status"] = "ja_existia_identico"
                else:
                    reg["status"] = "erro_destino_existe_com_outro_conteudo"; falhas += 1
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                tmp = dst.with_name(dst.name + ".tmp")
                shutil.copyfile(src, tmp)
                h_dst = sha256(tmp); reg["sha256_copia"] = h_dst
                if h_dst == p["sha256"]:
                    os.replace(tmp, dst); reg["status"] = "copiado"
                else:
                    reg["status"] = "erro_copia_corrompida (temporario mantido)"; falhas += 1
        except OSError as e:
            reg["status"] = f"erro: {type(e).__name__}: {e}"; falhas += 1
        log.append(reg)
        if i % 100 == 0 or i == len(acoes):
            print(f"  {i}/{len(acoes)}", end="\r")
    print()

    with open(saida / "log_operacoes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(log[0].keys())); w.writeheader(); w.writerows(log)
    if Path(a.inventario).exists():
        base.mkdir(parents=True, exist_ok=True)
        inv_dst = base / "inventario.csv"
        if not inv_dst.exists() or sha256(inv_dst) != sha256(a.inventario):
            shutil.copyfile(a.inventario, inv_dst)

    # ---------- verificação final ----------
    st = Counter(r["status"] for r in log)
    presentes = [d for d in destinos if d.is_file()]
    por_pasta = Counter(str(Path(d).parent.relative_to(base)).replace("\\", "/") for d in presentes)
    tmps = [q for q in base.rglob("*.tmp")] if base.exists() else []
    txt = [f"Organização executada em {agora()}",
           f"origem (somente leitura): {raiz}", f"destino: {base}",
           f"status: {dict(st)}",
           f"arquivos do plano presentes no destino: {len(presentes)} de {len(plano)}",
           f"arquivos temporários (.tmp) restantes: {len(tmps)}",
           f"arquivos no destino fora do plano: {len(extras)}",
           f"falhas: {falhas}", "", "Arquivos por pasta:"]
    txt += [f"  {p:40s} {q:4d}" for p, q in sorted(por_pasta.items())]
    (saida / "resumo_organizacao.txt").write_text("\n".join(txt) + "\n", encoding="utf-8")
    print("\n".join(txt))
    if falhas:
        raise SystemExit(f"{falhas} FALHAS: veja {saida / 'log_operacoes.csv'}. Nada foi apagado nem sobrescrito.")
    print("\nOK: todas as cópias conferidas por SHA-256. Os originais não foram alterados.")


if __name__ == "__main__":
    main()
