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


HISTORY_MSG = ("O template do cluster não é fonte de evidência: as respostas, observações e valores já preenchidos nele são histórico. "
               "A análise usa só os documentos do estado e o referencial ICE; o template entra na estrutura (códigos, classificações, layout) "
               "e no preenchimento da cópia. Para comparar com o histórico, use o comando paridade depois do resultado.")


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


def cmd_manifesto_montar(args):
    import esteira as ES
    import source_resolver as SR

    if not args.estado and not args.matriz:
        return emit(args, False, "manifesto-montar", "CLASSE_AUSENTE", "Informe ao menos um documento do estado (--estado).")
    if not args.template:
        return emit(args, False, "manifesto-montar", "CLASSE_AUSENTE", "Informe o template do cluster da UF (--template).")
    origens = {}
    for o in args.origem:
        path, sep, uri = o.partition("=")
        if not sep or not path.strip() or not uri.strip():
            return emit(args, False, "manifesto-montar", "ORIGEM_INVALIDA", "Use --origem \"<arquivo baixado>=<link da solicitação no Notion>\" (%s)." % o)
        origens[path.strip()] = uri.strip()
    m = ES.manifest(args.uf, args.ano, args.estado, args.template, args.ice, args.matriz, args.solicitacao, args.revisao, origens)
    if args.config_ice:  # approved ICE rules kept with the plugin (cloud flow): codes, minimum load, equivalences
        import ice_config as ICE

        m["configuracao_ice"] = ICE.read_rules_file(args.config_ice)
    SR.validate_manifest(m)
    out = Path(args.saida)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    ice = "%d arquivo(s) enviado(s)" % len(args.ice) if args.ice else "o referencial configurado no plugin"
    return emit(args, True, "manifesto-montar", "MANIFESTO_MONTADO", "Manifesto de %s %d gravado em %s: %d documento(s) do estado, %d template(s), referencial ICE: %s." % (
        m["uf"], m["ano"], out, len(args.estado) + len(args.matriz), len(args.template), ice), {"arquivo": str(out), "manifesto": m})


def cmd_template_preencher(args):
    import template_fill as TF

    r = TF.fill(Path(args.pasta), Path(args.saida) if args.saida else None, somente_uf=not args.todas_ufs)
    o = r["orientacoes"]
    msg = ("Template preenchido (cópia): %s. Pedagógicas: %d Sim, %d Não, %d Pendente; gestão: %d Sim, %d Não, %d Pendente; matriz: %d linha(s). "
           "Células em amarelo pedem decisão do analista. %sO template original não foi alterado." % (
               r["arquivo"], o["pedagogicas"]["Sim"], o["pedagogicas"]["Não"], o["pedagogicas"]["Pendente"], o["gestao"]["Sim"], o["gestao"]["Não"],
               o["gestao"]["Pendente"], r["linhas_matriz"], "" if args.todas_ufs else "Só a UF analisada fica visível; as outras UFs estão ocultas, não apagadas. ")) + ("" if not r["avisos"] else " Avisos: " + " ".join(r["avisos"]))
    if r["bloqueios"]:
        return emit(args, False, "template-preencher", "ENTREGA_BLOQUEADA", "A cópia foi gravada só para conferência e NÃO é uma entrega válida: " + "; ".join(r["bloqueios"])
                    + ". Ela não pode ser publicada no Notion. " + msg, r)
    return emit(args, True, "template-preencher", "TEMPLATE_PREENCHIDO", msg, r)


def cmd_esteira(args):
    import esteira as ES

    import quality_result as QR

    s = ES.status(Path(args.pasta))
    s["versao_plugin"] = QR.plugin_version()
    mark = {"feita": "[x]", "em_andamento": "[~]", "pendente": "[ ]"}
    lines = ["%s %d. %s — %s" % (mark[e["estado"]], i, e["titulo"], e["detalhe"]) for i, e in enumerate(s["etapas"], start=1)]
    if s["concluida"]:
        msg = "Esteira concluída: o template preenchido, o resultado e a fila de revisão estão prontos. Entregue primeiro o template preenchido, depois a fila."
    else:
        n = [e["etapa"] for e in s["etapas"]].index(s["proxima"]) + 1
        msg = "Próxima etapa: %d. %s. Comandos: %s." % (n, ES.TITLES[s["proxima"]], s["proximo_passo"])
    msg = "Plugin isg-model-alignment %s. %s" % (s["versao_plugin"], msg)
    return emit(args, True, "esteira", "ESTEIRA", msg, s, extra_text="\n".join(lines))


def cmd_iniciar(args):
    import quality_run as RUN

    inv = RUN.start_run(Path(args.manifesto), Path(args.pasta), ice_dir=args.referencial or None)
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
    if args.classe == "template_cluster":
        return emit(args, False, "buscar", "TEMPLATE_NAO_E_FONTE", HISTORY_MSG)
    hidden = {f["id"] for f in RUN.docs_of_class(inv, "template_cluster")}
    units = {k: v for k, v in units.items() if k not in hidden}  # the template's answers are history, never evidence
    if args.classe:
        allowed = {f["id"] for f in RUN.docs_of_class(inv, args.classe)}
        units = {k: v for k, v in units.items() if k in allowed}
    hits = DN.search(units, args.termo, args.limite)
    lines = ["%s [%s]: %s" % (h["unidade"], h["status"], h["trecho"]) for h in hits]
    return emit(args, True, "buscar", "BUSCA", "%d unidade(s) encontrada(s) para '%s'." % (len(hits), args.termo), {"resultados": hits}, extra_text="\n".join(lines))


def cmd_unidades(args):
    import quality_run as RUN

    inv = RUN.load_inventory(Path(args.pasta))
    if args.fonte in {f["id"] for f in RUN.docs_of_class(inv, "template_cluster")}:
        return emit(args, False, "unidades", "TEMPLATE_NAO_E_FONTE", HISTORY_MSG)
    units = RUN.load_units(Path(args.pasta), args.fonte).get(args.fonte)
    if units is None:
        return emit(args, False, "unidades", "FONTE_INEXISTENTE", "Fonte desconhecida: %s" % args.fonte)
    if args.pagina:  # PDF page numbers, with the image units of those pages (--de/--ate count units, not pages)
        lo, hi = args.pagina, args.ate_pagina or args.pagina
        sel = [u for u in units if lo <= (u["localizacao"].get("pagina") or 0) <= hi]
    else:
        sel = units[args.de - 1: args.ate] if args.ate else units[args.de - 1:]
    text = "\n\n".join("### %s [%s]\n%s" % (u["id"], u["status"], u.get("interpretacao_ia") or u["texto"]) for u in sel)
    return emit(args, True, "unidades", "UNIDADES", "%d de %d unidade(s) de %s." % (len(sel), len(units), args.fonte), {"unidades": sel}, extra_text=text)


def cmd_imagem_registrar(args):
    import quality_run as RUN

    text = Path(args.arquivo).read_text(encoding="utf-8")
    r = RUN.register_image_reading(Path(args.pasta), args.unidade, text, args.autor)
    copies = (" A mesma imagem estava em %s: a leitura foi copiada para lá." % ", ".join(r["copiada_para"])) if r["copiada_para"] else ""
    return emit(args, True, "imagem-registrar", "IMAGEM_REGISTRADA", "Leitura de imagem registrada em %s; ela fica marcada como feita por IA e precisa de conferência.%s" % (args.unidade, copies), r)


# ---------------- G2: matrix ----------------

def cmd_matriz_candidatas(args):
    import matrix_analysis as MA

    c = MA.candidates(Path(args.pasta))
    lines = ["%s: sinais %s; %d unidade(s), %d número(s)%s" % (x["regiao"], ", ".join(x["sinais"]) or "nenhum", x["unidades"], x["numeros"], "; em imagem" if x["em_imagem"] else "") for x in c]
    return emit(args, True, "matriz-candidatas", "CANDIDATAS", "%d região(ões) candidata(s) a matriz. O programa não escolhe: leia e confirme a oferta propedêutica de 9h." % len(c),
                {"candidatas": c}, extra_text="\n".join(lines))


def _matrix_message(s):
    msg = ("Matriz registrada: %d componente(s); células verificadas %d, em branco na fonte %d, não verificadas %d, em faixa %d; classificações pendentes %d; resumo: %s; completude: %s."
           % (s["componentes"], s["verificadas"], s["ausentes_na_fonte"], s["nao_verificadas"], s.get("em_faixa", 0), s["classificacoes_pendentes"], s["resumo"], s["completude"]))
    totals = s.get("totais_fonte") or []
    if totals:
        msg += " Totais impressos na fonte: %d fecham, %d não fecham, %d indeterminado(s)." % tuple(sum(t["estado"] == k for t in totals) for k in ("cabe", "nao_cabe", "indeterminado"))
    return msg


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


# ---------------- lessons of the MG 2026 pilot ----------------

def cmd_imagens(args):
    import quality_run as RUN

    pend = RUN.pending_images(Path(args.pasta))
    lines = ["%s: %s%s" % (p["unidade"], ("mesma imagem de %s (não precisa ler)" % p["mesma_imagem_que"]) if p["mesma_imagem_que"] else (", ".join(p["arquivos"]) or "sem arquivo exportado"),
                           ("; " + "; ".join(a for a in p["avisos"] if "não exportada" in a)) if not p["arquivos"] else "") for p in pend]
    unique = sum(1 for p in pend if not p["mesma_imagem_que"])
    return emit(args, True, "imagens", "IMAGENS", "%d trecho(s) em imagem aguardando leitura (SIP), %d imagem(ns) diferente(s). Leia só as diferentes e registre com imagem-registrar: "
                "a leitura é copiada para as repetidas. Muitas imagens: divida em lotes entre subagentes." % (len(pend), unique),
                {"imagens": pend, "imagens_diferentes": unique}, extra_text="\n".join(lines))


def cmd_tabela_pdf(args):
    import pdf_layout as PL
    import quality_run as RUN

    run = Path(args.pasta)
    idx = RUN.unit_index(run)
    if args.unidade not in idx or idx[args.unidade][1]["tipo"] != "pdf_page":
        return emit(args, False, "tabela-pdf", "UNIDADE_INVALIDA", "Informe uma página de PDF da execução (por exemplo DOC-2:p146).")
    doc_id, unit = idx[args.unidade]
    t = PL.page_table(next((run / "originais").glob(doc_id + ".pdf")), unit["localizacao"]["pagina"], args.colunas)
    lines = ["%-60s %s%s" % (r["rotulo"][:60], " | ".join(" ".join(g) if g else "·" for g in r["grupos"]), "  (incerta)" if r["incerta"] else "") for r in t["linhas"]]
    msg = "Tabela reconstruída pela posição do texto (%s, %d coluna(s) achada(s), grupo de %s número(s))%s. '·' = célula em branco." % (
        t["orientacao"], len(t["colunas"]), t["grupo"], (": " + "; ".join(t["avisos"])) if t["avisos"] else "")
    return emit(args, True, "tabela-pdf", "TABELA_PDF", msg, t, extra_text="\n".join(lines))


def cmd_orientacoes_lotes(args):
    import orientation_analysis as OA

    r = OA.export_batches(Path(args.pasta), Path(args.saida), args.tamanho)
    msg = "%d lote(s) gravado(s) em %s (%s). Cada avaliador lê documentos.md, INSTRUCOES.md e o seu lote; nada do preenchimento dos analistas foi exportado.%s" % (
        len(r["lotes"]), r["pasta"], ", ".join("%s: %s a %s" % (b["lote"], b["de"], b["ate"]) for b in r["lotes"]),
        "" if r["cobertura_completa"] else " Atenção: leitura incompleta em %s; nenhum Não será aceito até completar." % ", ".join(r["incompletos"]))
    return emit(args, True, "orientacoes-lotes", "LOTES", msg, r)


def cmd_orientacoes_conferir(args):
    import orientation_analysis as OA

    r = OA.check_proposals(Path(args.pasta), read_json_file(args.propostas))
    extra = "\n".join("%s: %s" % (p["codigo"], p["problema"]) for p in r["problemas"])
    msg = "%d orientação(ões) conferida(s), %d problema(s). Resultaria em Sim %d, Não %d, pendente %d. Nada foi registrado." % (
        r["orientacoes"], len(r["problemas"]), r["resultaria"]["sim"], r["resultaria"]["nao"], r["resultaria"]["pendente"])
    return emit(args, not r["problemas"], "orientacoes-conferir", "CONFERIDO" if not r["problemas"] else "PROBLEMAS", msg, r, extra_text=extra)


def cmd_revisao_fila(args):
    import quality_result as QR

    if not args.resultado and not args.pasta:
        return emit(args, False, "revisao-fila", "USO_INCORRETO", "Informe o arquivo do resultado ou --pasta da execução.", exit_code=EXIT_USAGE)
    path = Path(args.resultado) if args.resultado else Path(args.pasta) / QR.RESULT_FILE
    data = read_json_file(str(path))
    v = QR.validate(data)
    if not v["valido"]:
        return emit(args, False, "revisao-fila", "RESULTADO_INVALIDO", "A fila só é gerada de um resultado válido. Rode o comando validar para ver os erros.", v)
    if args.agrupada:
        g = QR.grouped_review_queue(data)
        if args.saida:
            Path(args.saida).write_text(json.dumps(g, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        lines = ["%d. %s [%s] — %s (%d item(ns) detalhado(s)%s)" % (x["ordem"], x["titulo"], x["id"], x["acao"], len(x["itens"]),
                                                                   ", %d célula(s)" % len(x["celulas"]) if x["celulas"] else "") for x in g["grupos"]]
        msg = ("%d tarefa(s) agrupada(s) para o analista, reunindo %d item(ns) da fila detalhada (%d célula(s) não verificada(s), %d em faixa). "
               "O número de tarefas não é o número de campos não verificados; a fila detalhada sai sem --agrupada." % (
                   g["total_grupos"], g["total_itens_detalhados"], g["celulas"]["nao_verificadas"], g["celulas"]["em_faixa"]))
        return emit(args, True, "revisao-fila", "FILA_AGRUPADA", msg, g, extra_text="\n".join(lines))
    q = QR.review_queue(data)
    if args.saida:
        Path(args.saida).write_text(json.dumps(q, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    lines = ["%d. %s (%s) — %s" % (i["ordem"], i["referencia"], i["tipo"], i["decisao"]) for i in q]
    return emit(args, True, "revisao-fila", "FILA", "%d decisão(ões) para o analista, da mais importante para a menos importante (fila detalhada; "
                "use --agrupada para a fila por tarefa)." % len(q), {"fila": q}, extra_text="\n".join(lines))


# ---------------- second pass (reanálise) ----------------

def cmd_reanalise_planejar(args):
    import second_pass as SP

    r = SP.plan(Path(args.pasta), Path(args.saida), args.tamanho)
    if r["ja_concluida"]:
        res = r["registro"]["resumo"]
        return emit(args, True, "reanalise-planejar", "REANALISE_JA_CONCLUIDA", "A segunda passagem já foi feita para estas entradas e não se repete (%d melhorada(s), "
                    "%d divergente(s), %d mantida(s)). Ela só reabre se as entradas mudarem." % (res["substituidas"], res["divergentes"], res["mantidas"]), r["registro"])
    msg = "%s segunda passagem: %d orientação(ões) em %d lote(s) em %s e %d componente(s) da matriz para segunda leitura (%s). Os lotes não trazem a decisão anterior." % (
        "Retomada a" if r["retomada"] else "Planejada a", r["orientacoes"], len(r["lotes"]), r["pasta"], r["componentes"], ", ".join(r["unidades_matriz"]) or "—")
    return emit(args, True, "reanalise-planejar", "REANALISE_PLANEJADA", msg, r)


def cmd_reanalise_registrar(args):
    import second_pass as SP

    r = SP.register_orientations(Path(args.pasta), read_json_file(args.propostas))
    msg = ("Segunda passagem registrada: %d melhorada(s) com evidência conferida, %d divergente(s) mantida(s) em revisão, %d sem evidência melhor, "
           "%d decisão(ões) do analista preservada(s); faltam %d." % (len(r["substituidas"]), len(r["divergentes"]), len(r["mantidas"]),
                                                                    len(r["preservadas_do_analista"]), len(r["faltam"])))
    if r["fora_da_selecao"] or r["ja_reavaliadas"]:
        msg += " Ignoradas: %s." % ", ".join(r["fora_da_selecao"] + r["ja_reavaliadas"])
    return emit(args, True, "reanalise-registrar", "REANALISE_REGISTRADA", msg, r)


def cmd_reanalise_matriz(args):
    import second_pass as SP

    r = SP.register_matrix(Path(args.pasta), read_json_file(args.leitura))
    msg = "Segunda leitura da matriz comparada: %d componente(s), %d conferem (continuam não verificados se vieram de imagem), %d divergem%s. Nenhum valor foi alterado." % (
        r["comparados"], r["conferem"], len(r["divergem"]), (": " + ", ".join(r["divergem"])) if r["divergem"] else "")
    return emit(args, True, "reanalise-matriz", "MATRIZ_RELIDA", msg, r)


def cmd_reanalise_documento(args):
    import second_pass as SP

    r = SP.request_document(Path(args.pasta), args.titulo, args.motivo, args.campos)
    return emit(args, True, "reanalise-documento", "DOCUMENTO_SOLICITADO", "Documento solicitado uma única vez: %s (%d campo(s) afetado(s)). Nada foi pesquisado nem baixado." % (
        r["titulo"], len(r["campos"])), r)


def cmd_reanalise_concluir(args):
    import second_pass as SP

    r = SP.finish(Path(args.pasta))
    msg = ("Segunda passagem concluída: %d de %d orientação(ões) reavaliada(s) — %d melhorada(s), %d divergente(s), %d mantida(s); %d componente(s) relido(s) de %d. "
           "Refaça o cruzamento, o resultado e o preenchimento." % (r["reavaliadas"], r["selecionadas"], r["substituidas"], r["divergentes"], r["mantidas"],
                                                                   r["componentes_relidos"], r["componentes_selecionados"]))
    return emit(args, True, "reanalise-concluir", "REANALISE_CONCLUIDA", msg, r)


# ---------------- publication in the Notion request ----------------

def cmd_publicar_localizar(args):
    import notion_publish as NP

    inv = __import__("quality_run").load_inventory(Path(args.pasta))
    r = NP.select_request(read_json_file(args.linhas), args.solicitacao, inv["uf"], inv["ano"])
    return emit(args, True, "publicar-localizar", "SOLICITACAO_LOCALIZADA", "Solicitação %s localizada sem ambiguidade: page_id %s." % (args.solicitacao, r["page_id"]), r)


def cmd_publicar_preparar(args):
    import notion_publish as NP

    r = NP.prepare(Path(args.pasta), args.pagina, args.solicitacao or None)
    if r["acao"] == "nada_a_fazer":
        return emit(args, True, "publicar-preparar", "JA_PUBLICADO", "Este arquivo (%s, sha256 %s) já está conferido nesta solicitação; nada a publicar." % (r["nome"], r["sha256"][:12]), r)
    return emit(args, True, "publicar-preparar", "PUBLICACAO_PREPARADA", "Publicação preparada: %s (%d bytes, sha256 %s) para a página %s. Próximo: ler a página pelo conector "
                "e rodar publicar-pagina. Nada foi enviado ao Notion ainda." % (r["nome"], r["tamanho_bytes"], r["sha256"][:12], r["page_id"]), r)


def cmd_publicar_pagina(args):
    import notion_publish as NP

    r = NP.check_page(Path(args.pasta), read_json_file(args.pagina_json))
    msg = ("Página conferida: é a solicitação desta execução (status atual: %s). " % (r["status_solicitacao"] or "—")) + (
        "O arquivo %s já está anexado: vá direto para publicar-confirmar." % r["nome"] if r["ja_anexado"] else "Pode criar o upload de %s pelo conector." % r["nome"])
    return emit(args, True, "publicar-pagina", "PAGINA_CONFERIDA", msg, r)


def cmd_publicar_enviar(args):
    import notion_publish as NP

    if args.url:
        r = NP.send(Path(args.pasta), args.url, read_json_file(args.cabecalhos) if args.cabecalhos else {}, args.upload_id)
    else:
        r = NP.record_upload(Path(args.pasta), args.upload_id, read_json_file(args.resposta) if args.resposta else None)
    return emit(args, True, "publicar-enviar", "ARQUIVO_ENVIADO", "Arquivo enviado ao Notion (upload %s), ainda NÃO anexado nem conferido. Próximo: publicar-propriedades." % r["file_upload_id"],
                {k: v for k, v in r.items() if k != "historico"})


def cmd_publicar_propriedades(args):
    import notion_publish as NP

    r = NP.properties_payload(Path(args.pasta), read_json_file(args.pagina_json))
    if args.saida and r["propriedades"]:
        Path(args.saida).write_text(json.dumps(r, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    msg = ("O arquivo já está na propriedade: nada a atualizar; releia a página e rode publicar-confirmar." if r["acao"] == "ja_anexado" else
           "Valor de 'Template Preenchido' montado (anexos anteriores mantidos + o novo upload). Grave com o conector (update_properties) e depois releia a página.")
    return emit(args, True, "publicar-propriedades", "PROPRIEDADES", msg, r)


def cmd_publicar_confirmar(args):
    import notion_publish as NP

    r = NP.confirm(Path(args.pasta), read_json_file(args.pagina_json))
    msg = "Publicação CONFIRMADA na página relida: %s está em 'Template Preenchido'. " % r["nome"] + (
        "Agora a solicitação pode ir para '%s'." % r["novo_status"] if r["novo_status"] else "O status não muda (%s)." % r["motivo_status"])
    return emit(args, True, "publicar-confirmar", "PUBLICACAO_CONFIRMADA", msg, r)


def cmd_publicar_execucao(args):
    import notion_publish as NP

    r = NP.execution_payload(Path(args.pasta), read_json_file(args.linhas) if args.linhas else [])
    if args.saida:
        Path(args.saida).write_text(json.dumps(r, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    msg = ("Linha de execução a CRIAR em 'Resultados — Execuções' (Validação humana = Aguardando)." if r["acao"] == "criar" else
           "Linha de execução existente a ATUALIZAR (%s), sem tocar na Validação humana." % r["page_id"])
    return emit(args, True, "publicar-execucao", "EXECUCAO", msg, r)


def cmd_publicar_falha(args):
    import notion_publish as NP

    r = NP.fail(Path(args.pasta), args.codigo, args.mensagem)
    return emit(args, True, "publicar-falha", "FALHA_REGISTRADA", "Falha de publicação registrada (%s); os arquivos ficam locais e a publicação pode ser retomada." % args.codigo, r)


# ---------------- the output in Notion (0.1.8: the only place the results are delivered) ----------------

def _write_out(args, data):
    if getattr(args, "saida", ""):
        Path(args.saida).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def cmd_notion_iniciar(args):
    import notion_results as NR

    r = NR.start(Path(args.pasta), read_json_file(args.pagina_json))
    return emit(args, True, "notion-iniciar", "SAIDA_INICIADA", "Solicitação conferida (%s, %s %d, execução %s). Grave nesta ordem: execucao, orientacoes, componentes, elementos, fila; "
                "depois o template (publicar-*) e, por fim, notion-entregar. Nada foi gravado no Notion ainda." % (r["solicitacao_id"], r["uf"], r["ano"], r["execucao_id"]), r)


def cmd_notion_linhas(args):
    import notion_publish as NP
    import notion_results as NR

    rows = NR.desired_rows(Path(args.pasta), args.base)
    data = {"base": args.base, "titulo": NR.BASE_TITLES[args.base], "data_source_id": NR.DATA_SOURCES[args.base], "linhas": rows}
    if args.base == "execucao":
        data["corpo"] = NR.execution_body(NP._result(Path(args.pasta)))
    _write_out(args, data)
    return emit(args, True, "notion-linhas", "LINHAS", "%s: %d linha(s) para esta execução." % (NR.BASE_TITLES[args.base], len(rows))
                + (" Sem linhas: a regra do template não está homologada (o motivo vai na linha da execução)." if args.base == "elementos" and not rows else ""), data)


def cmd_notion_planejar(args):
    import notion_results as NR

    r = NR.plan(Path(args.pasta), args.base, read_json_file(args.existentes) if args.existentes else [])
    _write_out(args, r)
    msg = "%s: criar %d, atualizar %d, manter %d%s%s. Grave pelo conector (só os campos listados; nunca os campos do analista), releia e rode notion-conferir." % (
        NR.BASE_TITLES[args.base], len(r["criar"]), len(r["atualizar"]), len(r["manter"]),
        ", %d bloqueada(s) pelo analista (não mexer)" % len(r["bloqueadas"]) if r["bloqueadas"] else "",
        ", %d obsoleta(s) (avise o analista; nada é apagado)" % len(r["obsoletas"]) if r["obsoletas"] else "")
    return emit(args, True, "notion-planejar", "PLANO", msg, r)


def cmd_notion_conferir(args):
    import notion_results as NR

    r = NR.confirm(Path(args.pasta), args.base, read_json_file(args.relidas))
    return emit(args, True, "notion-conferir", "BASE_CONFERIDA", "%s CONFERIDA na releitura: %d linha(s)." % (NR.BASE_TITLES[args.base], r["linhas"]), r)


def cmd_notion_entregar(args):
    import notion_results as NR

    r = NR.delivery(Path(args.pasta), args.status_atual or None)
    if not r["pronta"]:
        return emit(args, False, "notion-entregar", "ENTREGA_INCOMPLETA", "Ainda não: %s. O status da solicitação NÃO muda." % r["motivo"], r)
    msg = ("Tudo conferido no Notion: mude o Status da solicitação para '%s'." % r["novo_status"]) if r["novo_status"] else "Tudo conferido no Notion; o status não muda (%s)." % r["motivo"]
    return emit(args, True, "notion-entregar", "ENTREGA_CONFERIDA", msg, r)


def cmd_notion_falha(args):
    import notion_results as NR

    r = NR.fail(Path(args.pasta), args.base, args.codigo, args.mensagem)
    return emit(args, True, "notion-falha", "FALHA_REGISTRADA", "Falha registrada em %s (%s); a gravação pode ser retomada sem duplicar." % (args.base, args.codigo), r)


def cmd_ice_padrao(args):
    import ice_config as ICE

    try:
        cfg = ICE.load(args.referencial or None)
    except ICE.IceConfigError as e:
        return emit(args, False, "ice-padrao", e.code, e.message)
    hom = "homologação registrada por %s em %s" % (cfg["aprovado_por"], cfg["data"]) if cfg["homologacao"] else "aprovado por %s, sem data no manifesto_ice.json (a homologação fica pendente)" % cfg["aprovado_por"]
    data = {**cfg, "arquivos": [str(f) for f in cfg["arquivos"]]}
    return emit(args, True, "ice-padrao", "ICE_CONFIGURADO", "Referencial ICE configurado: versão %s, %s; %d arquivo(s). Deixe referencial_ice vazio no manifesto para usá-lo." % (cfg["versao"], hom, len(cfg["arquivos"])), data)


def cmd_sharepoint(args):
    import sharepoint_link as SP

    if not SP.is_sharepoint(args.link):
        return emit(args, False, "sharepoint", "NAO_E_SHAREPOINT", "Informe um link https de *.sharepoint.com. Outros endereços da internet não entram na análise.")
    r = SP.local_copy(args.link)
    link = r["link"]
    data = {"caminho_local": str(r["caminho"]) if r["caminho"] else None, "metodo": r["metodo"], "tipo_link": link["tipo"],
            "caminho_sharepoint": link["caminho"], "nome": link["nome"], "motivo": r["motivo"]}
    if r["caminho"]:
        how = "biblioteca sincronizada pelo OneDrive" if r["metodo"] == "biblioteca_sincronizada" else "atalho do OneDrive"
        return emit(args, True, "sharepoint", "COPIA_LOCAL", f"Cópia local encontrada ({how}): {r['caminho']}. Use o link no manifesto; o programa lê essa cópia.", data)
    return emit(args, False, "sharepoint", "SEM_COPIA_LOCAL", SP.missing_message(args.link, r["motivo"]), data)


HANDLERS = {
    "esquema": cmd_esquema, "manifesto-validar": cmd_manifesto_validar, "iniciar": cmd_iniciar, "inventario": cmd_inventario,
    "buscar": cmd_buscar, "unidades": cmd_unidades, "imagem-registrar": cmd_imagem_registrar,
    "matriz-candidatas": cmd_matriz_candidatas, "matriz-registrar": cmd_matriz_registrar, "matriz-confirmar": cmd_matriz_confirmar, "matriz-status": cmd_matriz_status,
    "orientacoes-codigos": cmd_orientacoes_codigos, "orientacoes-registrar": cmd_orientacoes_registrar, "orientacao-decidir": cmd_orientacao_decidir,
    "orientacoes-importar-eqv": cmd_orientacoes_importar_eqv, "orientacoes-status": cmd_orientacoes_status,
    "afirmacoes-registrar": cmd_afirmacoes_registrar, "cruzar": cmd_cruzar,
    "resultado": cmd_resultado, "validar": cmd_validar, "resumo": cmd_resumo, "paridade": cmd_paridade,
    "imagens": cmd_imagens, "tabela-pdf": cmd_tabela_pdf, "orientacoes-lotes": cmd_orientacoes_lotes, "orientacoes-conferir": cmd_orientacoes_conferir,
    "revisao-fila": cmd_revisao_fila, "sharepoint": cmd_sharepoint, "ice-padrao": cmd_ice_padrao,
    "manifesto-montar": cmd_manifesto_montar, "esteira": cmd_esteira, "template-preencher": cmd_template_preencher,
    "reanalise-planejar": cmd_reanalise_planejar, "reanalise-registrar": cmd_reanalise_registrar, "reanalise-matriz": cmd_reanalise_matriz,
    "reanalise-documento": cmd_reanalise_documento, "reanalise-concluir": cmd_reanalise_concluir,
    "publicar-localizar": cmd_publicar_localizar, "publicar-preparar": cmd_publicar_preparar, "publicar-pagina": cmd_publicar_pagina,
    "publicar-enviar": cmd_publicar_enviar, "publicar-propriedades": cmd_publicar_propriedades, "publicar-confirmar": cmd_publicar_confirmar,
    "publicar-execucao": cmd_publicar_execucao, "publicar-falha": cmd_publicar_falha,
    "notion-iniciar": cmd_notion_iniciar, "notion-linhas": cmd_notion_linhas, "notion-planejar": cmd_notion_planejar,
    "notion-conferir": cmd_notion_conferir, "notion-entregar": cmd_notion_entregar, "notion-falha": cmd_notion_falha,
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
    sp = add("manifesto-montar", run=False)
    sp.add_argument("--uf", required=True)
    sp.add_argument("--ano", type=int, required=True)
    sp.add_argument("--estado", nargs="*", default=[], help="documentos do estado (orientações e matriz): arquivos, pastas ou links do SharePoint")
    sp.add_argument("--matriz", nargs="*", default=[], help="documentos do estado que só trazem a matriz")
    sp.add_argument("--template", nargs="*", default=[], help="template do cluster da UF")
    sp.add_argument("--ice", nargs="*", default=[], help="referencial ICE enviado (vazio = o configurado no plugin)")
    sp.add_argument("--solicitacao", required=True, help="ID da solicitação no Notion (por exemplo QUA-13): identifica a execução e as chaves no Notion")
    sp.add_argument("--revisao", type=int, default=1, help="número da revisão desta solicitação (padrão 1; use 2 para refazer a análise)")
    sp.add_argument("--config-ice", default="", help="manifesto_ice.json aprovado (ou a pasta dele) com as regras da Qualidade: códigos, carga mínima, equivalências")
    sp.add_argument("--origem", action="append", default=[], help='"<arquivo baixado>=<link da solicitação no Notion>" para cada anexo baixado da solicitação (repetível)')
    sp.add_argument("--saida", required=True, help="arquivo manifesto.json a gravar")
    add("esteira")
    sp = add("template-preencher")
    sp.add_argument("--saida", default="", help="arquivo .xlsx a gravar (padrão: ao lado da pasta da execução)")
    sp.add_argument("--todas-ufs", action="store_true", help="mantém visíveis as abas e colunas das outras UFs (padrão: só a UF analisada fica visível)")
    sp = add("iniciar")
    sp.add_argument("manifesto")
    sp.add_argument("--referencial", default="", help="pasta do referencial ICE configurado (opção quality_ice_reference), usada se o manifesto deixar referencial_ice vazio")
    add("inventario")
    sp = add("buscar")
    sp.add_argument("--termo", required=True)
    sp.add_argument("--classe", choices=("orientacoes_estaduais", "matriz_estadual", "template_cluster", "referencial_ice"))
    sp.add_argument("--limite", type=int, default=30)
    sp = add("unidades")
    sp.add_argument("--fonte", required=True)
    sp.add_argument("--de", type=int, default=1)
    sp.add_argument("--ate", type=int, default=0)
    sp.add_argument("--pagina", type=int, default=0, help="página do PDF (com as imagens dela); use --ate-pagina para um intervalo")
    sp.add_argument("--ate-pagina", type=int, default=0)
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
    add("imagens")
    sp = add("tabela-pdf")
    sp.add_argument("--unidade", required=True, help="página de PDF, por exemplo DOC-2:p146")
    sp.add_argument("--colunas", type=int, default=3, help="número de séries da tabela (padrão 3)")
    sp = add("orientacoes-lotes")
    sp.add_argument("--saida", required=True, help="pasta onde gravar os lotes")
    sp.add_argument("--tamanho", type=int, default=35, help="orientações por lote (padrão 35)")
    add("orientacoes-conferir").add_argument("propostas")
    sp = add("revisao-fila", run=False)
    sp.add_argument("resultado", nargs="?", default="", help="resultado_qualidade.v1.json (ou use --pasta)")
    sp.add_argument("--pasta", default="", help="pasta da execução (lê <pasta>/resultado_qualidade.v1.json)")
    sp.add_argument("--agrupada", action="store_true", help="fila por tarefa (causa, ação e fonte comum); sem a opção, a fila detalhada para auditoria")
    sp.add_argument("--saida", default="")
    sp = add("reanalise-planejar")
    sp.add_argument("--saida", required=True, help="pasta onde gravar os lotes da segunda passagem")
    sp.add_argument("--tamanho", type=int, default=35)
    add("reanalise-registrar").add_argument("propostas", help="propostas da segunda passagem (mesmo formato de orientacoes-registrar)")
    add("reanalise-matriz").add_argument("leitura", help="matriz_segunda_leitura.json")
    sp = add("reanalise-documento")
    sp.add_argument("--titulo", required=True)
    sp.add_argument("--motivo", default="")
    sp.add_argument("--campos", nargs="+", required=True, help="campos afetados (por exemplo: C005 2ª série, EL2)")
    add("reanalise-concluir")
    sp = add("publicar-localizar")
    sp.add_argument("--solicitacao", required=True, help="ID de negócio (por exemplo QUA-12)")
    sp.add_argument("--linhas", required=True, help="JSON com as solicitações lidas pelo conector: [{page_id, id_solicitacao, uf, ano}]")
    sp = add("publicar-preparar")
    sp.add_argument("--pagina", required=True, help="page_id (ou link) da solicitação no Notion")
    sp.add_argument("--solicitacao", default="", help="ID de negócio da solicitação, para conferência")
    add("publicar-pagina").add_argument("--pagina-json", required=True, help="JSON da página lida pelo conector: {page_id, id_solicitacao, uf, ano, status, template_preenchido}")
    sp = add("publicar-enviar")
    sp.add_argument("--upload-id", required=True, help="id do upload criado pelo conector")
    sp.add_argument("--url", default="", help="URL de upload criada pelo conector (não é gravada)")
    sp.add_argument("--cabecalhos", default="", help="JSON com os cabeçalhos devolvidos pelo conector (não é gravado)")
    sp.add_argument("--resposta", default="", help="JSON da resposta do envio, quando o conector fez o envio")
    sp = add("publicar-propriedades")
    sp.add_argument("--pagina-json", required=True)
    sp.add_argument("--saida", default="")
    add("publicar-confirmar").add_argument("--pagina-json", required=True, help="JSON da página RELIDA depois da atualização")
    sp = add("publicar-execucao")
    sp.add_argument("--linhas", default="", help="JSON com as linhas de execução já existentes da solicitação: [{page_id, execucao}]")
    sp.add_argument("--saida", default="")
    sp = add("publicar-falha")
    sp.add_argument("--codigo", required=True)
    sp.add_argument("--mensagem", required=True)
    bases = ("execucao", "orientacoes", "componentes", "elementos", "fila")
    add("notion-iniciar").add_argument("--pagina-json", required=True, help="JSON da solicitação lida pelo conector: {page_id, id_solicitacao, uf, ano, status}")
    sp = add("notion-linhas")
    sp.add_argument("--base", required=True, choices=bases)
    sp.add_argument("--saida", default="")
    sp = add("notion-planejar")
    sp.add_argument("--base", required=True, choices=bases)
    sp.add_argument("--existentes", default="", help="JSON com as linhas desta execução já existentes na base (lidas pelo conector)")
    sp.add_argument("--saida", default="")
    sp = add("notion-conferir")
    sp.add_argument("--base", required=True, choices=bases)
    sp.add_argument("--relidas", required=True, help="JSON com as linhas relidas pelo conector depois da gravação")
    add("notion-entregar").add_argument("--status-atual", default="", help="Status atual da solicitação, relido pelo conector")
    sp = add("notion-falha")
    sp.add_argument("--base", required=True, choices=bases)
    sp.add_argument("--codigo", required=True)
    sp.add_argument("--mensagem", required=True)
    add("sharepoint", run=False).add_argument("link", help="link do SharePoint (arquivo ou pasta)")
    add("ice-padrao", run=False).add_argument("--referencial", default="", help="pasta do referencial ICE (opção quality_ice_reference)")
    return p


def main(argv):
    args = build_parser().parse_args(argv)
    if not args.comando:
        sys.stdout.write("Informe um comando: %s. Veja: resultado_qualidade.py --ajuda\n" % ", ".join(HANDLERS))
        return EXIT_USAGE
    import cross_check as CC
    import ice_config as ICE
    import matrix_analysis as MA
    import notion_publish as NP
    import notion_results as NR
    import second_pass as SP
    import template_fill as TF
    import orientation_analysis as OA
    import quality_run as RUN
    import source_resolver as SR

    try:
        return HANDLERS[args.comando](args)
    except SR.ManifestError as e:
        return emit(args, False, args.comando, e.code, e.message, {"erros": e.errors})
    except (RUN.RunError, MA.MatrixError, OA.OrientationError, CC.CrossCheckError, ICE.IceConfigError, TF.FillError, SP.SecondPassError, NP.PublishError, NR.NotionOutputError) as e:
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
