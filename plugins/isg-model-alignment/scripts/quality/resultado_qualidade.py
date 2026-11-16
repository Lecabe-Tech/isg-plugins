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


# ---------------- G3: orientations ----------------

def _orientation_message(s):
    parts = []
    for k, label in (("pedagogicas", "pedagógicas"), ("gestao", "gestão")):
        c = s["completude"][k]
        parts.append("%s: %s de %s aplicáveis decididas (Sim %d, Não %d), %d pendente(s), %d não avaliada(s), %d com revisão"
                     % (label, c["codigos_avaliados"], c["codigos_aplicaveis"] if c["codigos_aplicaveis"] is not None else "?", c["sim"], c["nao"], c["pendentes"], c["nao_avaliados"], c["revisar"]))
    return "Códigos: %s. %s." % (s["codigos"]["status"].replace("_", " "), "; ".join(parts))


def cmd_orientacoes_codigos(args):
    import orientation_analysis as OA

    s = OA.summary(Path(args.pasta))
    c = s["codigos"]
    extra = "Só no template: %s\nSó no ICE: %s\nAutoridade: %s" % (", ".join(c["somente_template"]) or "nenhum", ", ".join(c["somente_ice"]) or "nenhum", c["autoridade"] or "nenhuma")
    return emit(args, True, "orientacoes-codigos", "CODIGOS", _orientation_message(s), s, extra_text=extra)


def cmd_orientacoes_registrar(args):
    import orientation_analysis as OA

    r = OA.register(Path(args.pasta), read_json_file(args.propostas))
    s = OA.summary(Path(args.pasta))
    msg = "%d orientação(ões) registrada(s)%s%s. %s" % (len(r["registradas"]), ("; %d decisão(ões) do analista preservada(s)" % len(r["preservadas_do_analista"])) if r["preservadas_do_analista"] else "",
                                                       ("; códigos desconhecidos: " + ", ".join(r["codigos_desconhecidos"])) if r["codigos_desconhecidos"] else "", _orientation_message(s))
    extra = "\n".join("%s: %s (%s)%s" % (x["codigo"], x["presenca"] or "pendente", x["status"], (" — " + "; ".join(x["motivos"])) if x["motivos"] else "") for x in r["registradas"])
    return emit(args, True, "orientacoes-registrar", "ORIENTACOES_REGISTRADAS", msg, r, extra_text=extra)


def cmd_orientacao_decidir(args):
    import orientation_analysis as OA

    r = OA.analyst_decision(Path(args.pasta), args.codigo, args.presenca, args.justificativa, args.autor)
    return emit(args, True, "orientacao-decidir", "DECISAO_REGISTRADA", "Decisão do analista registrada: %s = %s. Uma nova execução da IA não a substitui." % (args.codigo, r["presenca"] or "pendente"), r)


def cmd_orientacoes_importar_eqv(args):
    import orientation_analysis as OA

    mapping = {}
    for item in args.mapa:
        label, _, doc = item.partition("=")
        if not label.strip() or not doc.strip():
            return emit(args, False, "orientacoes-importar-eqv", "USO_INCORRETO", 'Use --mapa "Rótulo na EQV=DOC-n".', exit_code=EXIT_USAGE)
        mapping[label.strip()] = doc.strip()
    r = OA.import_eqv(Path(args.pasta), Path(args.eqv), mapping)
    msg = "%d célula(s) da EQV importada(s) e conferida(s) de novo; %d Não sem prova suficiente virou pendência; %d decisão(ões) de analista preservada(s)." % (
        r["importadas"], r["convertidas_em_pendencia"], len(r["preservadas_do_analista"]))
    return emit(args, True, "orientacoes-importar-eqv", "EQV_IMPORTADA", msg, r)


def cmd_orientacoes_status(args):
    import orientation_analysis as OA

    s = OA.summary(Path(args.pasta))
    extra = "\n".join("- %s: %s" % (x["codigo"], x["detalhe"]) for x in s["pendencias"])
    return emit(args, True, "orientacoes-status", "ORIENTACOES_STATUS", _orientation_message(s), s, extra_text=extra)


# ---------------- G4: cross-check ----------------

def cmd_afirmacoes_registrar(args):
    import cross_check as CC

    r = CC.register(Path(args.pasta), read_json_file(args.afirmacoes))
    extra = "\n".join("%s rejeitada: %s" % (x["id"], "; ".join(x["motivos"])) for x in r["rejeitadas"])
    return emit(args, True, "afirmacoes-registrar", "AFIRMACOES_REGISTRADAS", "%d afirmação(ões) registrada(s), %d com citação conferida." % (r["afirmacoes"], r["verificadas"]), r, extra_text=extra)


def cmd_cruzar(args):
    import cross_check as CC

    r = CC.run(Path(args.pasta))
    extra = "\n".join("[%s] %s — %s: %s" % (c["gravidade"], c["codigo"], c["entidade"], c["detalhe"]) for c in r["conflitos"])
    return emit(args, True, "cruzar", "CRUZAMENTO", "Cruzamento feito: %d conflito(s) para revisão humana, %d checagem(ns) sem conflito. Nenhuma das frentes foi alterada."
                % (len(r["conflitos"]), sum(c["resultado"] == "sem_conflito" for c in r["checagens"])), r, extra_text=extra)


# ---------------- G5: final JSON, summary, parity ----------------

def cmd_resultado(args):
    import quality_result as QR

    r = QR.write(Path(args.pasta), Path(args.saida) if args.saida else None)
    if not r["ok"]:
        v = r["validacao"]
        return emit(args, False, "resultado", "RESULTADO_INVALIDO", "O resultado não passou na validação e não foi gravado: %s" % "; ".join((v["erros_schema"] + v["erros_semanticos"])[:8]),
                    {"validacao": v})
    e = r["resultado"]["execucao"]
    msg = "Resultado gravado e validado (%s): %s. Status: %s. Resumo para revisão: %s. Nada foi gravado no Excel, SharePoint, base central ou painel." % (
        e["id"], r["arquivo"], e["status"], r["resumo"])
    return emit(args, True, "resultado", "RESULTADO_GRAVADO", msg, {"arquivo": r["arquivo"], "resumo": r["resumo"], "status": e["status"], "conteudo_sha256": e["conteudo_sha256"],
                                                                   "pendencias": r["resultado"]["pendencias"]})


def cmd_validar(args):
    import quality_result as QR

    v = QR.validate(read_json_file(args.resultado))
    if v["valido"]:
        return emit(args, True, "validar", "RESULTADO_VALIDO", "O arquivo segue o schema v1 e as regras de consistência. Isso não significa análise aprovada: a revisão humana continua necessária.", v)
    return emit(args, False, "validar", "RESULTADO_INVALIDO", "O arquivo tem %d erro(s) de schema e %d de consistência." % (len(v["erros_schema"]), len(v["erros_semanticos"])), v,
                extra_text="\n".join(v["erros_schema"] + v["erros_semanticos"]))


def cmd_resumo(args):
    import quality_result as QR

    data = read_json_file(args.resultado)
    v = QR.validate(data)
    if not v["valido"]:
        return emit(args, False, "resumo", "RESULTADO_INVALIDO", "O resumo só é gerado de um resultado válido. Rode o comando validar para ver os erros.", v)
    text = QR.summary_md(data)
    return emit(args, True, "resumo", "RESUMO", "Resumo em português gerado do mesmo JSON.", {"markdown": text}, extra_text=text)


def cmd_paridade(args):
    import quality_result as QR

    data = read_json_file(args.resultado)
    if args.gabarito_template:
        key = QR.key_from_template(Path(args.gabarito_template), data["execucao"]["uf"], data["execucao"]["ano"])
    elif args.gabarito:
        key = read_json_file(args.gabarito)
    else:
        return emit(args, False, "paridade", "USO_INCORRETO", "Informe --gabarito-template (template preenchido) ou --gabarito (JSON).", exit_code=EXIT_USAGE)
    rep = QR.parity(data, key)
    if args.saida:
        Path(args.saida).write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    m, o = rep["matriz"], rep["orientacoes"]
    msg = ("Paridade com %s. Matriz: %d linha(s) pareada(s) de %d do gabarito; campos comparados %d, iguais %d, diferentes %d, sem valor no plugin %d. "
           "Orientações: comparadas %d, iguais %d, diferentes %d, sem decisão do plugin %d." % (
               rep["gabarito"], m["pareadas"], m["linhas_gabarito"], m["campos"]["comparados"], m["campos"]["iguais"], m["campos"]["diferentes"], m["campos"]["sem_valor_no_plugin"],
               o["comparadas"], o["iguais"], o["diferentes"], o["sem_decisao_no_plugin"]))
    extra = "\n".join(["%s %s: plugin %s, gabarito %s" % (d["componente"], d["campo"], d["plugin"], d["gabarito"]) for d in m["diferencas"]]
                      + ["%s: plugin %s, gabarito %s" % (d["codigo"], d["plugin"], d["gabarito"]) for d in o["diferencas"]])
    return emit(args, True, "paridade", "PARIDADE", msg, rep, extra_text=extra)


HANDLERS = {
    "esquema": cmd_esquema, "manifesto-validar": cmd_manifesto_validar, "iniciar": cmd_iniciar, "inventario": cmd_inventario,
    "buscar": cmd_buscar, "unidades": cmd_unidades, "imagem-registrar": cmd_imagem_registrar,
    "matriz-candidatas": cmd_matriz_candidatas, "matriz-registrar": cmd_matriz_registrar, "matriz-confirmar": cmd_matriz_confirmar, "matriz-status": cmd_matriz_status,
    "orientacoes-codigos": cmd_orientacoes_codigos, "orientacoes-registrar": cmd_orientacoes_registrar, "orientacao-decidir": cmd_orientacao_decidir,
    "orientacoes-importar-eqv": cmd_orientacoes_importar_eqv, "orientacoes-status": cmd_orientacoes_status,
    "afirmacoes-registrar": cmd_afirmacoes_registrar, "cruzar": cmd_cruzar,
    "resultado": cmd_resultado, "validar": cmd_validar, "resumo": cmd_resumo, "paridade": cmd_paridade,
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
    add("orientacoes-codigos")
    add("orientacoes-registrar").add_argument("propostas", help="JSON com a lista de orientações propostas (ver skill)")
    sp = add("orientacao-decidir")
    sp.add_argument("--codigo", required=True)
    sp.add_argument("--presenca", required=True, choices=("Sim", "Não", "Nao", "pendente"))
    sp.add_argument("--justificativa", required=True)
    sp.add_argument("--autor", required=True)
    sp = add("orientacoes-importar-eqv")
    sp.add_argument("--eqv", required=True, help="pasta da execução da EQV (com celulas/)")
    sp.add_argument("--mapa", action="append", default=[], required=True, help='"Rótulo na EQV=DOC-n" (repetível)')
    add("orientacoes-status")
    add("afirmacoes-registrar").add_argument("afirmacoes", help="JSON com afirmações tipadas (oferta, nao_oferta, carga_semanal, exigencia_normativa)")
    add("cruzar")
    add("resultado").add_argument("--saida", default="", help="arquivo de saída (padrão: <pasta>/resultado_qualidade.v1.json)")
    add("validar", run=False).add_argument("resultado")
    add("resumo", run=False).add_argument("resultado")
    sp = add("paridade", run=False)
    sp.add_argument("resultado")
    sp.add_argument("--gabarito-template", default="", help="template do cluster preenchido pelos analistas (cópia local)")
    sp.add_argument("--gabarito", default="", help="gabarito em JSON")
    sp.add_argument("--saida", default="")
    return p


def main(argv):
    args = build_parser().parse_args(argv)
    if not args.comando:
        sys.stdout.write("Informe um comando: %s. Veja: resultado_qualidade.py --ajuda\n" % ", ".join(HANDLERS))
        return EXIT_USAGE
    import cross_check as CC
    import matrix_analysis as MA
    import orientation_analysis as OA
    import quality_run as RUN
    import source_resolver as SR

    try:
        return HANDLERS[args.comando](args)
    except SR.ManifestError as e:
        return emit(args, False, args.comando, e.code, e.message, {"erros": e.errors})
    except (RUN.RunError, MA.MatrixError, OA.OrientationError, CC.CrossCheckError) as e:
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
