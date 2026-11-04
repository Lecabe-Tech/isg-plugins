#!/usr/bin/env python3
"""CFP command line (SPEC-003 4.3): processar | buscar | listar | pagina | status.

Contract (SPEC-001 4.8): non-interactive, --json prints ONE JSON object, exit codes 0 ok / 1 expected failure /
2 wrong usage / 3 unexpected error, messages for people in PT-BR, codes in English-ish identifiers.
This file must parse on old Pythons so that it can explain the Python-version problem.
"""
import sys

sys.dont_write_bytecode = True  # never write __pycache__ inside the plugin folder

if sys.version_info < (3, 11):
    sys.stdout.write("Python 3.11 ou mais novo é necessário para processar PDFs (versão atual: %d.%d). Instale em https://www.python.org/downloads/ e tente de novo.\n" % sys.version_info[:2])
    sys.exit(1)

import argparse  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
from pathlib import Path  # noqa: E402

for _stream in (sys.stdout, sys.stderr):  # PT-BR accents must come out as UTF-8 on every platform
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE / "vendor"))
sys.path.insert(0, str(HERE))

EXIT_OK, EXIT_FAIL, EXIT_USAGE, EXIT_UNEXPECTED = 0, 1, 2, 3


def emit(args, ok, command, code, message, data=None, exit_code=None, extra_text=None):
    result = {"ok": ok, "command": command, "code": code, "message": message, "data": data or {}}
    if getattr(args, "json", False):
        sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    else:
        parts = [message]
        if extra_text:
            parts += ["", extra_text]
        sys.stdout.write("\n".join(parts) + "\n")
    sys.stdout.flush()
    return exit_code if exit_code is not None else (EXIT_OK if ok else EXIT_FAIL)


class UsageParser(argparse.ArgumentParser):
    def error(self, message):  # PT-BR, exit code 2, no traceback
        raise SystemExit(self._usage_exit(message))

    def _usage_exit(self, message):
        wants_json = "--json" in sys.argv
        text = "Uso incorreto: %s. Veja: cfp.py --ajuda" % message
        if wants_json:
            sys.stdout.write(json.dumps({"ok": False, "command": "cfp", "code": "USO_INCORRETO", "message": text, "data": {}}, ensure_ascii=False) + "\n")
        else:
            sys.stdout.write(text + "\n")
        return EXIT_USAGE


def build_parser():
    p = UsageParser(prog="cfp.py", add_help=False, description="Processamento de PDFs em chunks (sem IA).")
    p.add_argument("--ajuda", "-h", action="help", help="mostra esta ajuda")
    sub = p.add_subparsers(dest="comando", parser_class=UsageParser)

    def common(sp):
        sp.add_argument("--json", action="store_true", help="uma saída JSON")
        sp.add_argument("--pasta-de-dados", default="", help="pasta de dados do plugin (padrão: pasta do aplicativo no sistema)")

    sp = sub.add_parser("processar", add_help=False)
    sp.add_argument("pdf")
    sp.add_argument("--uf", required=True)
    sp.add_argument("--ano", required=True)
    sp.add_argument("--titulo", default="")
    sp.add_argument("--force", action="store_true")
    sp.add_argument("--max-chars", type=int, default=12000)
    sp.add_argument("--min-chars", type=int, default=1500)
    sp.add_argument("--confirmar-grande", action="store_true")
    common(sp)

    sp = sub.add_parser("buscar", add_help=False)
    sp.add_argument("termos")
    sp.add_argument("--uf", default="")
    sp.add_argument("--ano", default="")
    sp.add_argument("--doc", default="")
    sp.add_argument("--max", type=int, default=50)
    common(sp)

    sp = sub.add_parser("listar", add_help=False)
    sp.add_argument("--uf", default="")
    sp.add_argument("--ano", default="")
    common(sp)

    sp = sub.add_parser("pagina", add_help=False)
    sp.add_argument("documento")
    sp.add_argument("numero", type=int)
    common(sp)

    sp = sub.add_parser("status", add_help=False)
    sp.add_argument("documento")
    common(sp)
    return p


def resolve_doc(cfp_root, ref):
    cand = Path(ref)
    if cand.is_dir():
        return cand
    cand = cfp_root / ref
    if cand.is_dir():
        return cand
    matches = [d for uf in cfp_root.glob("*") if uf.is_dir() for ano in uf.glob("*") if ano.is_dir() for d in ano.glob("*") if d.is_dir() and (d.name == ref or d.name.endswith("-" + ref))]
    return matches[0] if len(matches) == 1 else None


def cmd_processar(args, appdata):
    from isg_cfp.pipeline import CfpError, process_pdf

    def progress(done, total):
        if not args.json:
            sys.stderr.write("Processando… %d de %d páginas\n" % (done, total))
            sys.stderr.flush()

    try:
        r = process_pdf(args.pdf, args.uf, args.ano, appdata, titulo=args.titulo, force=args.force, max_chars=args.max_chars,
                        min_chars=args.min_chars, confirm_large=args.confirmar_grande, progress=progress)
    except CfpError as e:
        return emit(args, False, "processar", e.code, e.message)
    if r["codigo"] == "JA_PROCESSADO":
        return emit(args, True, "processar", "JA_PROCESSADO", "Este PDF já foi processado com esta versão (nada foi alterado). Pasta: %s. Situação: %s." % (r["pasta"], r["status"]), r)
    msg = "Documento processado: %d páginas em %d chunks. Situação de qualidade: %s. Pasta: %s." % (r["paginas"], r["chunks"], r["status"], r["caminho"])
    if r["status"] != "Aprovado":
        msg += " Leia qualidade.md antes de usar o conteúdo (%d página(s) com aviso)." % r["avisos"]
    return emit(args, True, "processar", "PROCESSADO", msg, r)


def cmd_buscar(args, appdata):
    from isg_cfp.search import search

    r = search(appdata / "cfp", args.termos, args.uf or None, args.ano or None, args.doc or None, args.max)
    if not r["termos"]:
        return emit(args, False, "buscar", "ENTRADA_INVALIDA", "Informe pelo menos um termo para buscar.")
    if r["total"] == 0:
        return emit(args, True, "buscar", "NADA_ENCONTRADO", "Nada encontrado para: %s." % args.termos, r)
    lines = ["%s | chunk %s | p. %d | %s" % (h["pasta"], h["chunk"], h["pagina"], h["trecho"]) for h in r["hits"]]
    more = "" if r["total"] <= len(r["hits"]) else "\n… e mais %d resultado(s)." % (r["total"] - len(r["hits"]))
    return emit(args, True, "buscar", "RESULTADOS", "%d resultado(s) para: %s." % (r["total"], args.termos), r, extra_text="\n".join(lines) + more)


def cmd_listar(args, appdata):
    from isg_cfp.search import list_documents

    docs = list_documents(appdata / "cfp", args.uf or None, args.ano or None)
    lines = ["%s %s | %s | %d págs | %d chunks | %s | %s%s" % (d["uf"], d["ano"], d["titulo"], d["paginas"], d["chunks"], d["status"], d["pasta"],
                                                          (" | SUBSTITUÍDO por " + d["substituido_por"]) if d.get("substituido_por") else "") for d in docs]
    return emit(args, True, "listar", "LISTA", "%d documento(s)." % len(docs), {"documentos": docs}, extra_text="\n".join(lines) or None)


def cmd_pagina(args, appdata):
    from isg_cfp.extract import open_reader, raw_plain_text
    from isg_cfp.search import split_pages

    d = resolve_doc(appdata / "cfp", args.documento)
    if d is None:
        return emit(args, False, "pagina", "DOCUMENTO_NAO_ENCONTRADO", "Documento não encontrado: %s. Use `cfp listar`." % args.documento)
    n = args.numero
    organised = None
    for chunk in sorted((d / "chunks").glob("*.md")):
        for page, text in split_pages(chunk.read_text(encoding="utf-8")):
            if page == n:
                organised = (organised + "\n" if organised else "") + "[chunk %s]\n%s" % (chunk.stem, text.strip())
    reader, err = open_reader(d / "original.pdf")
    if organised is None or reader is None or not (1 <= n <= len(reader.pages)):
        return emit(args, False, "pagina", "PAGINA_INEXISTENTE", "Página %d não existe neste documento." % n)
    raw = raw_plain_text(reader, n - 1)
    text = "=== Texto bruto extraído pelo pypdf (p. %d) ===\n%s\n\n=== Texto organizado nos chunks (p. %d) ===\n%s" % (n, raw, n, organised)
    return emit(args, True, "pagina", "PAGINA", "Página %d de %s." % (n, d.name), {"bruto": raw, "organizado": organised}, extra_text=text)


def cmd_status(args, appdata):
    d = resolve_doc(appdata / "cfp", args.documento)
    if d is None:
        return emit(args, False, "status", "DOCUMENTO_NAO_ENCONTRADO", "Documento não encontrado: %s. Use `cfp listar`." % args.documento)
    q = json.loads((d / "qualidade.json").read_text(encoding="utf-8"))
    idx = json.loads((d / "index.json").read_text(encoding="utf-8"))
    flagged = idx.get("paginas_com_avisos", {})
    msg = "%s: %s (%s páginas, %s chunks, %d página(s) com aviso). Leia %s." % (d.name, q["situacao"], idx["paginas"], len(idx["chunks"]), len(flagged), d / "qualidade.md")
    return emit(args, True, "status", "STATUS", msg, {"situacao": q["situacao"], "verificacoes": q["verificacoes"], "paginas_com_avisos": flagged})


def main(argv):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.comando:
        sys.stdout.write("Informe um comando: processar, buscar, listar, pagina ou status. Veja: cfp.py --ajuda\n")
        return EXIT_USAGE
    try:
        import isg_cfp  # noqa: F401
        from isg_cfp.appdata import ensure_appdata, resolve_appdata
        try:
            import pypdf  # noqa: F401  (vendored)
        except Exception:
            return emit(args, False, args.comando, "DEPENDENCIA_AUSENTE", "A biblioteca pypdf incluída no plugin não pôde ser carregada. Reinstale ou atualize o plugin.")
        appdata = resolve_appdata(args.pasta_de_dados)
        try:
            ensure_appdata(appdata, PLUGIN_ROOT)
        except ValueError as e:
            return emit(args, False, args.comando, "PASTA_INVALIDA", str(e))
        except OSError as e:
            return emit(args, False, args.comando, "PASTA_INVALIDA", "Não consegui criar a pasta de dados (%s). Escolha outra pasta." % e.strerror)
        handler = {"processar": cmd_processar, "buscar": cmd_buscar, "listar": cmd_listar, "pagina": cmd_pagina, "status": cmd_status}[args.comando]
        return handler(args, appdata)
    except SystemExit:
        raise
    except Exception as e:  # unexpected: never a traceback for the analyst
        msg = "Erro inesperado: %s. Tente de novo; se continuar, avise a equipe responsável pelo plugin." % re.sub(r"\s+", " ", str(e))[:200]
        return emit(args, False, args.comando, "ERRO_INESPERADO", msg, exit_code=EXIT_UNEXPECTED)


if __name__ == "__main__":
    sys.stdin = open(os.devnull, "r") if sys.stdin is not None else None
    sys.exit(main(sys.argv[1:]))
