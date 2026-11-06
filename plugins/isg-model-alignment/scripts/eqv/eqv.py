#!/usr/bin/env python3
"""EQV command line (SPEC-005): modelo | iniciar | inventario-registrar | inventario-status | celula-registrar | decidir | exportar | status | medir.

Contract (SPEC-001 4.8): non-interactive, --json prints ONE JSON object, exit codes 0 ok / 1 expected failure /
2 wrong usage / 3 unexpected error, messages for people in PT-BR. The engine never calls the AI: the skill proposes,
this program verifies the quotes, applies the rules and writes the files.
"""
import sys

sys.dont_write_bytecode = True

if sys.version_info < (3, 11):
    sys.stdout.write("Python 3.11 ou mais novo é necessário (versão atual: %d.%d). Instale em https://www.python.org/downloads/ e tente de novo.\n" % sys.version_info[:2])
    sys.exit(1)

import argparse  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
from pathlib import Path  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "cfp"))  # appdata helpers of CFP (one application-data folder for everything)

EXIT_OK, EXIT_FAIL, EXIT_USAGE, EXIT_UNEXPECTED = 0, 1, 2, 3


def emit(args, ok, command, code, message, data=None, exit_code=None, extra_text=None):
    result = {"ok": ok, "command": command, "code": code, "message": message, "data": data or {}}
    if getattr(args, "json", False):
        sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    else:
        sys.stdout.write("\n".join([message] + (["", extra_text] if extra_text else [])) + "\n")
    sys.stdout.flush()
    return exit_code if exit_code is not None else (EXIT_OK if ok else EXIT_FAIL)


class UsageParser(argparse.ArgumentParser):
    def error(self, message):
        raise SystemExit(self._usage_exit(message))

    def _usage_exit(self, message):
        text = "Uso incorreto: %s. Veja: eqv.py --ajuda" % message
        if "--json" in sys.argv:
            sys.stdout.write(json.dumps({"ok": False, "command": "eqv", "code": "USO_INCORRETO", "message": text, "data": {}}, ensure_ascii=False) + "\n")
        else:
            sys.stdout.write(text + "\n")
        return EXIT_USAGE


def build_parser():
    p = UsageParser(prog="eqv.py", add_help=False, description="Comparação de orientações do Instituto com documentos de um estado.")
    p.add_argument("--ajuda", "-h", action="help", help="mostra esta ajuda")
    sub = p.add_subparsers(dest="comando", parser_class=UsageParser)

    def common(sp, run=True):
        sp.add_argument("--json", action="store_true")
        sp.add_argument("--pasta-de-dados", default="")
        if run:
            sp.add_argument("--uf", required=True)
            sp.add_argument("--ano", required=True, type=int)

    sp = sub.add_parser("modelo", add_help=False)
    sp.add_argument("planilha")
    sp.add_argument("--saida", default="")
    common(sp, run=False)

    sp = sub.add_parser("iniciar", add_help=False)
    sp.add_argument("planilha")
    sp.add_argument("--doc", action="append", default=[], help='"Rótulo=pasta do documento no CFP" (repetível)')
    common(sp)

    sp = sub.add_parser("inventario-registrar", add_help=False)
    sp.add_argument("rotulo")
    sp.add_argument("arquivo", help="JSON com itens: grupo, titulo, descricao, pagina, trecho (e chunk)")
    sp.add_argument("--chunks", default="", help="trechos cobertos nesta passada, por exemplo 1-12 ou 3,4,5")
    common(sp)

    sp = sub.add_parser("inventario-status", add_help=False)
    common(sp)

    sp = sub.add_parser("celula-registrar", add_help=False)
    sp.add_argument("arquivo", help="JSON com uma célula (ou lista): aba, codigo, valor, confianca, explicacao, evidencias, ausencia")
    sp.add_argument("--minimo", type=int, default=85)
    common(sp)

    sp = sub.add_parser("decidir", add_help=False)
    sp.add_argument("aba")
    sp.add_argument("codigo")
    sp.add_argument("--valor", required=True)
    sp.add_argument("--motivo", default="")
    sp.add_argument("--autor", default="")
    common(sp)

    sp = sub.add_parser("exportar", add_help=False)
    common(sp)
    sp = sub.add_parser("status", add_help=False)
    common(sp)
    sp = sub.add_parser("medir", add_help=False)
    common(sp)
    return p


def parse_chunks(text: str) -> list:
    out = []
    for part in re.split(r"[,\s]+", text.strip()):
        if not part:
            continue
        a, _, b = part.partition("-")
        if a.isdigit():
            out += list(range(int(a), int(b or a) + 1)) if (not b or b.isdigit()) else []
    return out


def cmd_modelo(args, appdata):
    from isg_eqv.template import TemplateError, read_template, summarize

    path = Path(args.planilha)
    if not path.is_file():
        return emit(args, False, "modelo", "ENTRADA_INVALIDA", "Não encontrei o arquivo: %s" % path)
    try:
        t = read_template(path)
    except TemplateError as e:
        return emit(args, False, "modelo", e.code, e.message)
    data = {"sha256": t["sha256"], "abas": {k: {"orientacoes": len(v["orientacoes"]), "colunas": v["colunas"], "avisos": v["avisos"]} for k, v in t["abas"].items()},
            "respostas_dos_analistas": len(t["gabarito"]), "avisos": t["avisos"]}
    if args.saida:
        out = Path(args.saida)
        out.mkdir(parents=True, exist_ok=True)
        orient = {tab: a["orientacoes"] for tab, a in t["abas"].items()}
        (out / "orientacoes.json").write_text(json.dumps({"sha256": t["sha256"], "colunas": {k: v["colunas"] for k, v in t["abas"].items()}, "orientacoes": orient}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        (out / "gabarito.json").write_text(json.dumps(t["gabarito"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        data["pasta"] = str(out)
    msg = "Planilha lida (nada foi alterado nela): " + summarize(t)
    if t["avisos"]:
        msg += " Avisos: %d." % len(t["avisos"])
    return emit(args, True, "modelo", "MODELO_LIDO", msg, data)


def _rd(args, appdata):
    from isg_eqv.store import run_dir

    return run_dir(appdata, args.uf, args.ano)


def cmd_iniciar(args, appdata):
    from isg_eqv import store as S

    template = Path(args.planilha)
    if not template.is_file():
        return emit(args, False, "iniciar", "ENTRADA_INVALIDA", "Não encontrei o arquivo: %s" % template)
    docs = [S.parse_doc_arg(d) for d in args.doc]
    r = S.start_run(appdata, template, args.uf, args.ano, docs, appdata / "cfp")
    msg = ("Comparação iniciada para %s %d (%s). Documentos: %s. Para montar o inventário será preciso ler cerca de %d mil caracteres dos documentos (estimativa aproximada: %d mil a %d mil tokens do seu plano)."
           % (args.uf.upper(), args.ano, ", ".join("aba %s: %d orientações" % (k, v) for k, v in sorted(r["abas"].items())), ", ".join(r["documentos"]), round(r["caracteres"] / 1000), round(r["tokens_min"] / 1000), round(r["tokens_max"] / 1000)))
    return emit(args, True, "iniciar", "INICIADA", msg, r)


def cmd_inventario_registrar(args, appdata):
    from isg_eqv import store as S

    items = json.loads(Path(args.arquivo).read_text(encoding="utf-8"))
    r = S.register_inventory(_rd(args, appdata), args.rotulo, items.get("itens", items) if isinstance(items, dict) else items, parse_chunks(args.chunks))
    msg = "Inventário de '%s': %d item(ns) aceito(s), %d rejeitado(s) (citação não confere). Trechos cobertos: %d de %d." % (args.rotulo, r["aceitos"], len(r["rejeitados"]), r["chunks_cobertos"], r["chunks_do_documento"])
    return emit(args, True, "inventario-registrar", "INVENTARIO_REGISTRADO", msg, r)


def cmd_inventario_status(args, appdata):
    from isg_eqv import store as S

    r = S.inventory_status(_rd(args, appdata))
    lines = ["%s: %d item(ns); trechos cobertos %d de %d%s" % (k, v["itens"], v["chunks_cobertos"], v["chunks"], " (completo)" if v["completo"] else "") for k, v in r.items()]
    return emit(args, True, "inventario-status", "INVENTARIO", "Situação dos inventários.", r, extra_text="\n".join(lines))


def cmd_celula_registrar(args, appdata):
    from isg_eqv import store as S

    data = json.loads(Path(args.arquivo).read_text(encoding="utf-8"))
    items = data if isinstance(data, list) else [data]
    rd = _rd(args, appdata)
    results = [S.register_cell(rd, it, args.minimo) for it in items]
    flagged = sum(1 for r in results if r.get("revisar"))
    kept = sum(1 for r in results if r.get("mantida"))
    msg = "%d célula(s) registrada(s): %s. %d com Revisar%s." % (len(results) - kept, ", ".join("%s %s%s" % (r["codigo"], r["valor"], " (revisar)" if r.get("revisar") else "") for r in results[:12]) + (" …" if len(results) > 12 else ""), flagged,
                                                                  ("; %d decisão(ões) de analista preservada(s)" % kept) if kept else "")
    return emit(args, True, "celula-registrar", "CELULAS_REGISTRADAS", msg, {"celulas": results})


def cmd_decidir(args, appdata):
    from isg_eqv import store as S

    r = S.decide(_rd(args, appdata), args.aba, args.codigo, args.valor, args.motivo, args.autor)
    return emit(args, True, "decidir", "DECIDIDA", "Decisão do analista registrada: %s = %s (confiança 95%%; sem Revisar). Ela não será sobrescrita por uma nova execução." % (args.codigo, r["valor"]), r)


def cmd_exportar(args, appdata):
    from isg_eqv import export as X

    r = X.export(_rd(args, appdata))
    c = r["comparacao_completa"]
    msg = "Arquivos gravados em %s. Comparação completa: %s.%s" % (r["pasta"], "sim" if c["completo"] else "não", (" Falta: " + "; ".join(c["motivos"]) + ".") if c["motivos"] else "")
    return emit(args, True, "exportar", "EXPORTADO", msg, r)


def cmd_status(args, appdata):
    from isg_eqv import store as S

    r = S.status(_rd(args, appdata))
    lines = ["aba %s: %d de %d comparadas (Sim %d, Não %d, Revisar %d)" % (t, v["comparadas"], v["orientacoes"], v["sim"], v["nao"], v["revisar"]) for t, v in sorted(r["abas"].items())]
    return emit(args, True, "status", "STATUS", "Andamento da comparação.", r, extra_text="\n".join(lines))


def cmd_medir(args, appdata):
    from isg_eqv import export as X

    m = X.measure(_rd(args, appdata))
    msg = "Concordância com os analistas: %s%% em %d célula(s) avaliada(s) (%d falso Sim, %d falso Não); %d célula(s) fora da medida por citarem outros documentos; %d com Revisar." % (
        m["concordancia_pct"], m["avaliadas"], m["falso_sim"], m["falso_nao"], m["excluidas_outros_documentos"], m["revisar"])
    return emit(args, True, "medir", "MEDIDA", msg, m)


HANDLERS = {"modelo": cmd_modelo, "iniciar": cmd_iniciar, "inventario-registrar": cmd_inventario_registrar, "inventario-status": cmd_inventario_status,
            "celula-registrar": cmd_celula_registrar, "decidir": cmd_decidir, "exportar": cmd_exportar, "status": cmd_status, "medir": cmd_medir}


def main(argv):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.comando:
        sys.stdout.write("Informe um comando: %s. Veja: eqv.py --ajuda\n" % ", ".join(HANDLERS))
        return EXIT_USAGE
    try:
        from isg_cfp.appdata import ensure_appdata, resolve_appdata
        from isg_eqv.store import EqvError
        from isg_eqv.template import TemplateError

        appdata = resolve_appdata(getattr(args, "pasta_de_dados", ""))
        try:
            if args.comando != "modelo":  # reading the template needs no data folder
                ensure_appdata(appdata, PLUGIN_ROOT)
        except ValueError as e:
            return emit(args, False, args.comando, "PASTA_INVALIDA", str(e))
        except OSError as e:
            return emit(args, False, args.comando, "PASTA_INVALIDA", "Não consegui criar a pasta de dados (%s). Escolha outra pasta." % e.strerror)
        try:
            return HANDLERS[args.comando](args, appdata)
        except (EqvError, TemplateError) as e:
            return emit(args, False, args.comando, e.code, e.message)
        except json.JSONDecodeError:
            return emit(args, False, args.comando, "JSON_INVALIDO", "O arquivo JSON informado não é válido.")
        except OSError as e:
            return emit(args, False, args.comando, "ARQUIVO_ILEGIVEL", "Não consegui ler ou gravar um arquivo (%s)." % e.strerror)
    except SystemExit:
        raise
    except Exception as e:
        msg = "Erro inesperado: %s. Tente de novo; se continuar, avise a equipe responsável pelo plugin." % re.sub(r"\s+", " ", str(e))[:200]
        return emit(args, False, args.comando, "ERRO_INESPERADO", msg, exit_code=EXIT_UNEXPECTED)


if __name__ == "__main__":
    sys.stdin = open(os.devnull, "r") if sys.stdin is not None else None
    sys.exit(main(sys.argv[1:]))
