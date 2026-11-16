#!/usr/bin/env python3
"""SPEC-017 command line: four inputs -> matrix + orientations -> cross-check -> resultado_qualidade.v1.json.

Contract (SPEC-001 4.8): non-interactive, --json prints ONE JSON object, exit codes 0 ok / 1 expected failure /
2 wrong usage / 3 unexpected error, messages for people in PT-BR. The program never calls an AI: Claude proposes
(JSON files), this program verifies quotes and cells, applies the rules and writes the run folder. Nothing is written
to Excel, SharePoint, the central base or any BI.
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

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

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
        text = "Uso incorreto: %s. Veja: resultado_qualidade.py --ajuda" % message
        if "--json" in sys.argv:
            sys.stdout.write(json.dumps({"ok": False, "command": "resultado_qualidade", "code": "USO_INCORRETO", "message": text, "data": {}}, ensure_ascii=False) + "\n")
        else:
            sys.stdout.write(text + "\n")
        raise SystemExit(EXIT_USAGE)


def read_json_file(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ---------------- G0 / G1 ----------------

def cmd_esquema(args):
    import schema_check

    sys.stdout.write(json.dumps(schema_check.load_schema(args.tipo), ensure_ascii=False, indent=2) + "\n")
    return EXIT_OK


def cmd_manifesto_validar(args):
    import source_resolver as SR

    m = SR.validate_manifest(read_json_file(args.manifesto))
    counts = {c: len(m["entradas"][c]) for c in SR.CLASSES}
    msg = "Manifesto válido para %s %d (propedêutico 9h): %s." % (m["uf"], m["ano"], ", ".join("%s %d" % (SR.CLASS_LABEL[c], n) for c, n in counts.items()))
    if not m.get("homologacao_ice"):
        msg += " Atenção: sem registro de homologação do ICE, o resultado nunca será completo."
    return emit(args, True, "manifesto-validar", "MANIFESTO_VALIDO", msg, {"entradas": counts})


def cmd_iniciar(args):
    import quality_run as RUN

    inv = RUN.start_run(Path(args.manifesto), Path(args.pasta))
    lines = []
    for f in inv["fontes"]:
        cov = f["cobertura"]
        lines.append("%s (%s) %s: %s; %d unidade(s), %d pendente(s)%s" % (
            f["id"], ", ".join(f["classes"]), f["nome"], f["status_leitura"], cov["unidades_total"], cov["unidades_pendentes"],
            ("; " + "; ".join(p["detalhe"] for p in f["pendencias"])) if f["pendencias"] else ""))
    pend = sum(len(f["pendencias"]) for f in inv["fontes"]) + len(inv["pendencias"])
    msg = "Execução iniciada para %s %d: %d documento(s) inventariado(s), %d pendência(s) de entrada." % (inv["uf"], inv["ano"], len(inv["fontes"]), pend)
    return emit(args, True, "iniciar", "INICIADA", msg, inv, extra_text="\n".join(lines))


def cmd_inventario(args):
    import quality_run as RUN

    inv = RUN.load_inventory(Path(args.pasta))
    lines = ["%s %s: %s (%d/%d unidades lidas)" % (f["id"], f["nome"], f["status_leitura"], f["cobertura"]["unidades_lidas"], f["cobertura"]["unidades_total"]) for f in inv["fontes"]]
    return emit(args, True, "inventario", "INVENTARIO", "Inventário das fontes da execução.", inv, extra_text="\n".join(lines))


def cmd_buscar(args):
    import document_normalizer as DN
    import quality_run as RUN

    run = Path(args.pasta)
    inv = RUN.load_inventory(run)
    units = RUN.load_units(run)
    if args.classe:
        allowed = {f["id"] for f in RUN.docs_of_class(inv, args.classe)}
        units = {k: v for k, v in units.items() if k in allowed}
    hits = DN.search(units, args.termo, args.limite)
    lines = ["%s [%s]: %s" % (h["unidade"], h["status"], h["trecho"]) for h in hits]
    return emit(args, True, "buscar", "BUSCA", "%d unidade(s) encontrada(s) para '%s'." % (len(hits), args.termo), {"resultados": hits}, extra_text="\n".join(lines))


def cmd_unidades(args):
    import quality_run as RUN

    units = RUN.load_units(Path(args.pasta), args.fonte).get(args.fonte)
    if units is None:
        return emit(args, False, "unidades", "FONTE_INEXISTENTE", "Fonte desconhecida: %s" % args.fonte)
    sel = units[args.de - 1: args.ate] if args.ate else units[args.de - 1:]
    text = "\n\n".join("### %s [%s]\n%s" % (u["id"], u["status"], u.get("interpretacao_ia") or u["texto"]) for u in sel)
    return emit(args, True, "unidades", "UNIDADES", "%d de %d unidade(s) de %s." % (len(sel), len(units), args.fonte), {"unidades": sel}, extra_text=text)


def cmd_imagem_registrar(args):
    import quality_run as RUN

    text = Path(args.arquivo).read_text(encoding="utf-8")
    r = RUN.register_image_reading(Path(args.pasta), args.unidade, text, args.autor)
    return emit(args, True, "imagem-registrar", "IMAGEM_REGISTRADA", "Leitura de imagem registrada em %s; ela fica marcada como feita por IA e precisa de conferência." % args.unidade, r)


# ---------------- G2: matrix ----------------

def cmd_matriz_candidatas(args):
    import matrix_analysis as MA

    c = MA.candidates(Path(args.pasta))
    lines = ["%s: sinais %s; %d unidade(s), %d número(s)%s" % (x["regiao"], ", ".join(x["sinais"]) or "nenhum", x["unidades"], x["numeros"], "; em imagem" if x["em_imagem"] else "") for x in c]
    return emit(args, True, "matriz-candidatas", "CANDIDATAS", "%d região(ões) candidata(s) a matriz. O programa não escolhe: leia e confirme a oferta propedêutica de 9h." % len(c),
                {"candidatas": c}, extra_text="\n".join(lines))


def _matrix_message(s):
    return ("Matriz registrada: %d componente(s); células verificadas %d, em branco na fonte %d, não verificadas %d; classificações pendentes %d; resumo: %s; completude: %s."
            % (s["componentes"], s["verificadas"], s["ausentes_na_fonte"], s["nao_verificadas"], s["classificacoes_pendentes"], s["resumo"], s["completude"]))


def cmd_matriz_registrar(args):
    import matrix_analysis as MA

    s = MA.register(Path(args.pasta), read_json_file(args.proposta))
    extra = "\n".join("%s %s: %s" % (r["id"], r["nome"], "; ".join(r["motivos"])) for r in s["revisar"])
    return emit(args, True, "matriz-registrar", "MATRIZ_REGISTRADA", _matrix_message(s), s, extra_text=extra)


def cmd_matriz_confirmar(args):
    import matrix_analysis as MA

    sel = MA.confirm(Path(args.pasta), args.autor, args.motivo)
    return emit(args, True, "matriz-confirmar", "MATRIZ_CONFIRMADA", "Seleção da matriz confirmada por %s." % sel["confirmacao"]["autor"], sel)


def cmd_matriz_status(args):
    import matrix_analysis as MA

    s = MA.summary(Path(args.pasta))
    extra = "\n".join("- %s: %s" % (x["codigo"], x["detalhe"]) for x in s["pendencias"])
    return emit(args, True, "matriz-status", "MATRIZ_STATUS", _matrix_message(s).replace("Matriz registrada", "Matriz"), s, extra_text=extra)


HANDLERS = {
    "esquema": cmd_esquema, "manifesto-validar": cmd_manifesto_validar, "iniciar": cmd_iniciar, "inventario": cmd_inventario,
    "buscar": cmd_buscar, "unidades": cmd_unidades, "imagem-registrar": cmd_imagem_registrar,
    "matriz-candidatas": cmd_matriz_candidatas, "matriz-registrar": cmd_matriz_registrar, "matriz-confirmar": cmd_matriz_confirmar, "matriz-status": cmd_matriz_status,
}


def build_parser():
    p = UsageParser(prog="resultado_qualidade.py", add_help=False, description="Análise de Qualidade (SPEC-017): matriz 9h e orientações com evidências.")
    p.add_argument("--ajuda", "-h", action="help", help="mostra esta ajuda")
    sub = p.add_subparsers(dest="comando", parser_class=UsageParser)

    def add(name, run=True):
        sp = sub.add_parser(name, add_help=False)
        sp.add_argument("--json", action="store_true")
        if run:
            sp.add_argument("--pasta", required=True, help="pasta da execução")
        return sp

    sp = add("esquema", run=False)
    sp.add_argument("--tipo", choices=("manifesto", "resultado"), default="resultado")
    add("manifesto-validar", run=False).add_argument("manifesto")
    add("iniciar").add_argument("manifesto")
    add("inventario")
    sp = add("buscar")
    sp.add_argument("--termo", required=True)
    sp.add_argument("--classe", choices=("orientacoes_estaduais", "matriz_estadual", "template_cluster", "referencial_ice"))
    sp.add_argument("--limite", type=int, default=30)
    sp = add("unidades")
    sp.add_argument("--fonte", required=True)
    sp.add_argument("--de", type=int, default=1)
    sp.add_argument("--ate", type=int, default=0)
    sp = add("imagem-registrar")
    sp.add_argument("--unidade", required=True)
    sp.add_argument("--arquivo", required=True, help="texto (Markdown) da leitura da imagem feita pela skill SIP")
    sp.add_argument("--autor", default="SIP")
    add("matriz-candidatas")
    add("matriz-registrar").add_argument("proposta", help="JSON com seleção, duração da hora-aula e componentes (ver skill)")
    sp = add("matriz-confirmar")
    sp.add_argument("--autor", required=True)
    sp.add_argument("--motivo", default="")
    add("matriz-status")
    return p


def main(argv):
    args = build_parser().parse_args(argv)
    if not args.comando:
        sys.stdout.write("Informe um comando: %s. Veja: resultado_qualidade.py --ajuda\n" % ", ".join(HANDLERS))
        return EXIT_USAGE
    import matrix_analysis as MA
    import quality_run as RUN
    import source_resolver as SR

    try:
        return HANDLERS[args.comando](args)
    except SR.ManifestError as e:
        return emit(args, False, args.comando, e.code, e.message, {"erros": e.errors})
    except (RUN.RunError, MA.MatrixError) as e:
        return emit(args, False, args.comando, e.code, e.message)
    except json.JSONDecodeError:
        return emit(args, False, args.comando, "JSON_INVALIDO", "O arquivo JSON informado não é válido.")
    except FileNotFoundError as e:
        return emit(args, False, args.comando, "ARQUIVO_INEXISTENTE", "Arquivo não encontrado: %s" % e.filename)
    except OSError as e:
        return emit(args, False, args.comando, "ARQUIVO_ILEGIVEL", "Não consegui ler ou gravar um arquivo (%s)." % e.strerror)
    except Exception as e:  # noqa: BLE001
        msg = "Erro inesperado: %s. Tente de novo; se continuar, avise a equipe responsável pelo plugin." % re.sub(r"\s+", " ", str(e))[:200]
        return emit(args, False, args.comando, "ERRO_INESPERADO", msg, exit_code=EXIT_UNEXPECTED)


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    sys.stdin = open(os.devnull, "r") if sys.stdin is not None else None
    sys.exit(main(sys.argv[1:]))
