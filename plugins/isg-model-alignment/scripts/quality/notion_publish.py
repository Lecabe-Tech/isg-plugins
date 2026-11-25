"""Publication of the filled template in the Notion request (Solicitações de Análise de Alinhamento ao Modelo).

The program never talks to Notion by itself and never claims an upload it did not see. It is the deterministic half of
the publication; the authenticated Notion connector of the session is the other half:

  1. `prepare`     : checks the request page id, the result, the filled copy (valid delivery, same result, same bytes),
                     computes the SHA-256 and a deterministic file name, and records `publicacao.json` (idempotent: a
                     publication already confirmed for the same page and bytes is not repeated);
  2. `check_page`  : before ANY write, the page read through the connector must be the same request (page id, business
                     id, UF, year). There is no "most recent request" fallback: without a page id, `select_request`
                     accepts a lookup by business id only when exactly one request matches;
  3. upload        : the connector creates the file upload (short-lived URL); `send` posts the bytes to it (or the
                     connector does and `record_upload` stores the upload id). The URL is never stored or logged;
  4. `properties_payload`: the 'Template Preenchido' (files) value = the files already there + the new upload, so
                     earlier runs' attachments are kept; a page that already has this exact file needs no update;
  5. `confirm`     : the page READ AGAIN must show the file; only then the publication is `confirmada` and the request
                     may move to 'Aguardando Validação' (never back from 'Aguardando Validação' or 'Concluído');
  6. `execution_payload`: the linked row in 'Resultados — Execuções', found by its execution id (create or update, never
                     duplicate), with 'Validação humana = Aguardando' only when it is created: a human validation is
                     never overwritten.
A failure is recorded (`fail`) with the local files kept, so the publication resumes without re-running the analysis.
Nothing here holds tokens, signed URLs or real request data; 'Link Template Preenchimento' (the input file) is never touched.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path

import quality_result as QR
import quality_run as RUN
import source_resolver as SR
import template_fill as TF

DATABASE_ID = "4203eb42-d128-8140-895e-f3d4e5f1d4dc"
DATA_SOURCE_ID = "4203eb42-d128-819c-870a-000b1aad1405"
EXECUTIONS_DATA_SOURCE_ID = "4223eb42-d128-8159-8ae8-000bce611135"
PROP_OUTPUT = "Template Preenchido"
PROP_INPUT = "Link Template Preenchimento"
PROP_STATUS = "Status"
STATUS_DELIVERED = "Aguardando Validação"
STATUS_NO_REGRESS = {"Aguardando Validação", "Concluído"}
FILE = "publicacao.json"
MAX_BYTES = 20 * 1024 * 1024  # single-part upload limit of the connector


class PublishError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def normalize_page_id(value) -> str | None:
    """A Notion page id from a raw id or a page URL -> dashed lowercase UUID, or None."""
    m = re.findall(r"[0-9a-fA-F]{32}|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", str(value or ""))
    if not m:
        return None
    return str(uuid.UUID(m[-1].replace("-", "")))


def _norm_business_id(v) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(v or "").upper())


def _ufs(v) -> list:
    if isinstance(v, str):
        return [v.strip().upper()] if v.strip() else []
    return sorted({str(x).strip().upper() for x in v or [] if str(x).strip()})


def file_name(result: dict) -> str:
    e = result["execucao"]
    return re.sub(r"[^A-Za-z0-9._-]", "-", f"{e['id']}-{e['uf']}-{e['ano']}-template-preenchido.xlsx")


def _load(run_dir: Path) -> dict | None:
    return SR.read_json(Path(run_dir) / FILE)


def _save(run_dir: Path, pub: dict) -> None:
    SR.write_json(Path(run_dir) / FILE, pub)


def _sha256(path: Path) -> str:
    return TF.file_sha256(path)


def select_request(rows: list, solicitacao_id: str, uf: str, ano: int) -> dict:
    """The one request whose business id, UF and year match. Zero or several -> error: never the most recent one."""
    key = _norm_business_id(solicitacao_id)
    if not key:
        raise PublishError("SOLICITACAO_SEM_ID", "Sem o page_id e sem o ID de negócio da solicitação não há como identificá-la; a entrega fica local.")
    same_id = [r for r in rows if _norm_business_id(r.get("id_solicitacao")) == key]
    match = [r for r in same_id if _ufs(r.get("uf")) == [uf.upper()] and int(r.get("ano") or 0) == int(ano)]
    if len(match) != 1:
        code = "SOLICITACAO_NAO_ENCONTRADA" if not match else "SOLICITACAO_AMBIGUA"
        raise PublishError(code, f"{len(match)} solicitação(ões) com ID {solicitacao_id}, UF {uf} e ano {ano} (com o mesmo ID: {len(same_id)}). "
                                 "A publicação só segue com exatamente uma; a entrega fica local e a falha foi registrada.")
    pid = normalize_page_id(match[0].get("page_id"))
    if not pid:
        raise PublishError("SOLICITACAO_SEM_ID", "A solicitação encontrada não trouxe o page_id.")
    return {**match[0], "page_id": pid}


def _result(run_dir: Path) -> dict:
    path = Path(run_dir) / QR.RESULT_FILE
    if not path.exists():
        raise PublishError("RESULTADO_AUSENTE", "Gere e valide o resultado antes de publicar.")
    result = json.loads(path.read_text(encoding="utf-8"))
    if not QR.validate(result)["valido"]:
        raise PublishError("RESULTADO_INVALIDO", "O resultado não passa na validação; nada é publicado.")
    return result


def _delivery(run_dir: Path, result: dict) -> tuple:
    rec = SR.read_json(Path(run_dir) / TF.RECORD_FILE)
    if not rec:
        raise PublishError("TEMPLATE_NAO_PREENCHIDO", "Rode template-preencher antes de publicar.")
    if not rec.get("entrega_valida"):
        raise PublishError("ENTREGA_BLOQUEADA", "A cópia preenchida não é entrega válida: " + "; ".join(rec.get("bloqueios") or ["motivo não registrado"]) + ".")
    if rec.get("resultado_sha256") != result["execucao"]["conteudo_sha256"]:
        raise PublishError("XLSX_DESATUALIZADO", "A cópia preenchida é de um resultado anterior; rode template-preencher de novo. Nunca se publica um Excel de resultado anterior.")
    xlsx = Path(rec["arquivo"])
    if not xlsx.is_file():
        raise PublishError("XLSX_AUSENTE", f"O arquivo preenchido não existe mais: {xlsx}.")
    sha = _sha256(xlsx)
    if sha != rec.get("arquivo_sha256"):
        raise PublishError("XLSX_ALTERADO", "O arquivo preenchido mudou depois do preenchimento (hash diferente); rode template-preencher de novo.")
    if xlsx.stat().st_size > MAX_BYTES:
        raise PublishError("XLSX_GRANDE_DEMAIS", "O arquivo passa de 20 MiB, o limite do envio em uma parte; a entrega fica local.")
    return xlsx, sha


def prepare(run_dir: Path, page_id, solicitacao_id: str | None = None) -> dict:
    run_dir = Path(run_dir)
    pid = normalize_page_id(page_id)
    if not pid:
        raise PublishError("SOLICITACAO_SEM_ID", "Informe o page_id da solicitação do Notion (ou localize-a pelo ID de negócio com publicar-localizar). "
                                                 "Nunca se escolhe a solicitação mais recente.")
    result = _result(run_dir)
    e = result["execucao"]
    if solicitacao_id and _norm_business_id(solicitacao_id) != _norm_business_id(e["solicitacao_id"]):
        raise PublishError("SOLICITACAO_DIVERGENTE", f"A execução é da solicitação {e['solicitacao_id']}, não de {solicitacao_id}.")
    xlsx, sha = _delivery(run_dir, result)
    pub = _load(run_dir)
    name = file_name(result)
    if pub and pub["status"] == "confirmada":
        if pub["page_id"] == pid and pub["sha256"] == sha:
            return {**pub, "acao": "nada_a_fazer"}
        if pub["page_id"] != pid:
            raise PublishError("PAGINA_DIFERENTE", f"Esta execução já foi publicada em outra solicitação ({pub['page_id']}); confira o page_id.")
    history = (pub or {}).get("historico", [])
    if pub and pub["status"] == "confirmada":
        history = history + [{k: pub[k] for k in ("sha256", "file_upload_id", "confirmada_em")}]
    pub = {"page_id": pid, "solicitacao_id": e["solicitacao_id"], "execucao_id": e["id"], "uf": e["uf"], "ano": e["ano"], "arquivo": str(xlsx), "nome": name,
           "sha256": sha, "tamanho_bytes": xlsx.stat().st_size, "resultado_sha256": e["conteudo_sha256"], "status": "preparada", "file_upload_id": None,
           "anexos_anteriores": None, "pagina_conferida": False, "preparada_em": RUN.now(), "enviada_em": None, "confirmada_em": None, "erro": None,
           "historico": history}
    _save(run_dir, pub)
    return {**pub, "acao": "publicar"}


def _open(run_dir: Path, *states) -> dict:
    pub = _load(run_dir)
    if not pub:
        raise PublishError("PUBLICACAO_NAO_PREPARADA", "Rode publicar-preparar antes.")
    if states and pub["status"] not in states:
        raise PublishError("ETAPA_FORA_DE_ORDEM", f"A publicação está em '{pub['status']}'; esta etapa vale para: {', '.join(states)}.")
    return pub


def check_page(run_dir: Path, page: dict) -> dict:
    """The page as read through the connector BEFORE any write. Same page id, business id, UF and year, or nothing is written."""
    run_dir = Path(run_dir)
    pub = _open(run_dir)
    problems = []
    if normalize_page_id(page.get("page_id")) != pub["page_id"]:
        problems.append(f"page_id lido {page.get('page_id')} ≠ {pub['page_id']}")
    if page.get("id_solicitacao") is not None and _norm_business_id(page["id_solicitacao"]) != _norm_business_id(pub["solicitacao_id"]):
        problems.append(f"ID da solicitação {page['id_solicitacao']} ≠ {pub['solicitacao_id']}")
    if _ufs(page.get("uf")) != [pub["uf"]]:
        problems.append(f"UF {page.get('uf')} ≠ {pub['uf']}")
    try:
        same_year = int(page.get("ano")) == int(pub["ano"])
    except (TypeError, ValueError):
        same_year = False
    if not same_year:
        problems.append(f"ano {page.get('ano')} ≠ {pub['ano']}")
    if problems:
        fail(run_dir, "SOLICITACAO_DIVERGENTE", "; ".join(problems))
        raise PublishError("SOLICITACAO_DIVERGENTE", "A página não é a solicitação desta execução (" + "; ".join(problems) + "). Nada foi gravado no Notion.")
    pub = _load(run_dir)
    pub["pagina_conferida"] = True
    pub["status_solicitacao_lido"] = page.get("status")
    _save(run_dir, pub)
    files = page.get("template_preenchido") or []
    already = any(f.get("nome") == pub["nome"] for f in files)
    return {"ok": True, "ja_anexado": already, "status_solicitacao": page.get("status"), "nome": pub["nome"]}


def record_upload(run_dir: Path, file_upload_id: str, response: dict | None = None) -> dict:
    run_dir = Path(run_dir)
    pub = _open(run_dir, "preparada", "enviada", "falhou")
    if not pub["pagina_conferida"]:
        raise PublishError("PAGINA_NAO_CONFERIDA", "Confira a página da solicitação (publicar-pagina) antes de enviar o arquivo.")
    fid = str(file_upload_id or "").strip()
    if not re.fullmatch(r"[0-9a-fA-F-]{32,36}", fid):
        raise PublishError("UPLOAD_INVALIDO", "O id do upload do Notion é inválido.")
    if response is not None:
        if str(response.get("status")) != "uploaded":
            fail(run_dir, "UPLOAD_FALHOU", f"o Notion respondeu status {response.get('status')!r}")
            raise PublishError("UPLOAD_FALHOU", f"O Notion não confirmou o envio (status {response.get('status')!r}); nada foi anexado.")
        if response.get("filename") and response["filename"] != pub["nome"]:
            raise PublishError("UPLOAD_INVALIDO", f"O upload é de outro arquivo ({response['filename']}).")
        if response.get("id") and normalize_page_id(response["id"]) != normalize_page_id(fid):
            raise PublishError("UPLOAD_INVALIDO", "A resposta do envio é de outro upload.")
    pub.update(status="enviada", file_upload_id=fid, enviada_em=RUN.now(), erro=None)
    _save(run_dir, pub)
    return pub


def _multipart(name: str, data: bytes, content_type: str) -> tuple:
    boundary = "----isg" + uuid.uuid4().hex
    head = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\nContent-Type: {content_type}\r\n\r\n').encode("utf-8")
    return head + data + f"\r\n--{boundary}--\r\n".encode("utf-8"), f"multipart/form-data; boundary={boundary}"


XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def send(run_dir: Path, upload_url: str, headers: dict, file_upload_id: str, opener=None) -> dict:
    """Posts the file to the short-lived upload URL created by the connector (single part, `file` field, every header the
    connector returned). The URL and the headers are not stored."""
    run_dir = Path(run_dir)
    pub = _open(run_dir, "preparada", "falhou")
    if not pub["pagina_conferida"]:
        raise PublishError("PAGINA_NAO_CONFERIDA", "Confira a página da solicitação (publicar-pagina) antes de enviar o arquivo.")
    if not str(upload_url or "").startswith("https://"):
        raise PublishError("URL_INVALIDA", "Use a URL https de upload criada pelo conector do Notion.")
    path = Path(pub["arquivo"])
    if _sha256(path) != pub["sha256"]:
        raise PublishError("XLSX_ALTERADO", "O arquivo mudou depois de publicar-preparar; prepare de novo.")
    body, ctype = _multipart(pub["nome"], path.read_bytes(), XLSX_TYPE)
    hdrs = {str(k): str(v) for k, v in (headers or {}).items() if str(k).lower() != "content-type"}
    hdrs["Content-Type"] = ctype
    if opener is None:
        import urllib.request

        opener = urllib.request.urlopen
        req = urllib.request.Request(upload_url, data=body, headers=hdrs, method="POST")
    else:
        req = {"url": upload_url, "data": body, "headers": hdrs, "method": "POST"}
    try:
        with opener(req, timeout=120) as resp:
            payload = json.loads(resp.read().decode("utf-8") or "{}")
    except Exception as exc:  # noqa: BLE001  (network or HTTP error: recorded, files kept, resumable)
        fail(run_dir, "UPLOAD_FALHOU", re.sub(r"https://\S+", "<url>", str(exc))[:200])
        raise PublishError("UPLOAD_FALHOU", "O envio do arquivo ao Notion falhou; a entrega fica local e pode ser retomada (publicar-preparar não precisa refazer a análise).")
    return record_upload(run_dir, file_upload_id, payload)


def properties_payload(run_dir: Path, page: dict) -> dict:
    """Value for the 'Template Preenchido' files property: the files already there (by id) + the new upload. If this
    exact file is already attached, no update is needed. An existing entry without id would be lost: refused."""
    run_dir = Path(run_dir)
    pub = _open(run_dir, "enviada")
    if normalize_page_id(page.get("page_id")) != pub["page_id"]:
        raise PublishError("SOLICITACAO_DIVERGENTE", "A página lida não é a da publicação preparada.")
    files = page.get("template_preenchido") or []
    if any(f.get("nome") == pub["nome"] for f in files):
        return {"acao": "ja_anexado", "propriedades": None}
    missing = [f.get("nome") or "?" for f in files if not f.get("id")]
    if missing:
        raise PublishError("ANEXOS_SEM_ID", "A propriedade já tem arquivo(s) sem id (" + ", ".join(missing) + "); atualizar apagaria esses anexos. Nada foi gravado.")
    pub["anexos_anteriores"] = [{"nome": f.get("nome"), "id": f["id"]} for f in files]
    _save(run_dir, pub)
    value = [f["id"] for f in files] + [{"type": "file_upload", "file_upload": {"id": pub["file_upload_id"]}}]
    return {"acao": "atualizar", "page_id": pub["page_id"], "propriedades": {PROP_OUTPUT: value}}


def confirm(run_dir: Path, page_after: dict) -> dict:
    """The page READ AGAIN after the update. Confirmed only if the file is there and the earlier attachments too."""
    run_dir = Path(run_dir)
    pub = _open(run_dir, "enviada", "confirmada")
    if normalize_page_id(page_after.get("page_id")) != pub["page_id"]:
        raise PublishError("SOLICITACAO_DIVERGENTE", "A página relida não é a da publicação.")
    files = page_after.get("template_preenchido") or []
    names = [f.get("nome") for f in files]
    if pub["nome"] not in names:
        fail(run_dir, "ARQUIVO_NAO_ENCONTRADO_NA_PAGINA", f"{pub['nome']} não aparece em {PROP_OUTPUT}")
        raise PublishError("ARQUIVO_NAO_ENCONTRADO_NA_PAGINA", f"O arquivo {pub['nome']} não aparece em '{PROP_OUTPUT}' na página relida: a publicação NÃO está confirmada.")
    lost = [a["nome"] for a in pub.get("anexos_anteriores") or [] if a["nome"] not in names]
    if lost:
        fail(run_dir, "ANEXOS_PERDIDOS", ", ".join(lost))
        raise PublishError("ANEXOS_PERDIDOS", "Anexos anteriores sumiram da propriedade: " + ", ".join(lost) + ". Confira a página antes de qualquer outra escrita.")
    first_time = pub["status"] != "confirmada"
    pub.update(status="confirmada", confirmada_em=pub.get("confirmada_em") if not first_time else RUN.now(), erro=None)
    current = page_after.get("status")
    pub["status_solicitacao_lido"] = current
    _save(run_dir, pub)
    new_status = None if current in STATUS_NO_REGRESS else STATUS_DELIVERED
    return {"confirmada": True, "nome": pub["nome"], "page_id": pub["page_id"], "status_atual": current, "novo_status": new_status,
            "motivo_status": "a solicitação já está em '%s'; não se regride o status" % current if new_status is None else
            f"arquivo conferido na página: a solicitação pode ir para '{STATUS_DELIVERED}'"}


def execution_payload(run_dir: Path, rows: list) -> dict:
    """Row of 'Resultados — Execuções' for this run. rows: the rows already there for this request ({'page_id',
    'execucao'}). Create (with 'Validação humana' = Aguardando) or update (never touching the human validation)."""
    run_dir = Path(run_dir)
    pub = _open(run_dir, "confirmada")
    result = _result(run_dir)
    e = result["execucao"]
    title = f"{e['uf']} {e['ano']} — {e['id']}"
    same = [r for r in rows if _norm_business_id(r.get("execucao")) == _norm_business_id(title)]
    if len(same) > 1:
        raise PublishError("EXECUCAO_DUPLICADA", f"Há {len(same)} linhas para a execução {e['id']}; resolva a duplicata no Notion antes de atualizar.")
    o = result["orientacoes"]["completude"]
    mins = result["matriz"]["minutos_aula"]
    props = {"Execução": title, "UF": e["uf"], "Ano": e["ano"], "Revisão": e["revisao"], "Modalidade": "propedêutico 9h", "Motor": e["motor_versao"],
             "Status Claude": e["status"] if e["status"] in ("parcial", "completo") else "erro",
             "Sim (Claude)": sum(o[k]["sim"] for k in ("pedagogicas", "gestao")), "Não (Claude)": sum(o[k]["nao"] for k in ("pedagogicas", "gestao")),
             "Pendentes (Claude)": sum(o[k]["pendentes"] for k in ("pedagogicas", "gestao")),
             "Itens na fila": len(QR.review_queue(result)), "Hora-aula (min)": mins["valor"] if mins["status"] == "verificado" else None,
             "SHA-256 conteúdo": e["conteudo_sha256"], "date:Gerado em:start": e["gerado_em"], "date:Gerado em:is_datetime": 1,
             "Observações": "\n".join(sorted({p["codigo"] for p in result["pendencias"] if p["bloqueia_completude"]})) or None,
             "Solicitação": [pub["page_id"]]}
    if same:
        return {"acao": "atualizar", "page_id": normalize_page_id(same[0].get("page_id")), "propriedades": props,
                "observacao": "'Validação humana' não é enviada: a decisão do analista nunca é sobrescrita."}
    return {"acao": "criar", "data_source_id": EXECUTIONS_DATA_SOURCE_ID, "propriedades": {**props, "Validação humana": "Aguardando"}}


def fail(run_dir: Path, code: str, message: str) -> dict:
    pub = _load(Path(run_dir))
    if not pub:
        return {}
    if pub["status"] != "confirmada":
        pub["status"] = "falhou"
    pub["erro"] = {"codigo": code, "mensagem": message, "em": RUN.now()}
    _save(Path(run_dir), pub)
    return pub


def pipeline_state(run_dir: Path) -> dict | None:
    """None when the run never started a publication (no Notion request); otherwise its stage state."""
    pub = _load(Path(run_dir))
    if not pub:
        return None
    rec = SR.read_json(Path(run_dir) / TF.RECORD_FILE) or {}
    if pub["status"] == "confirmada" and rec.get("arquivo_sha256") == pub["sha256"]:
        return {"estado": "feita", "detalhe": f"{pub['nome']} conferido na solicitação ({pub['page_id']})."}
    if pub["status"] == "confirmada":
        return {"estado": "pendente", "detalhe": "O template preenchido mudou depois da última publicação: publique de novo."}
    if pub["status"] == "falhou":
        return {"estado": "pendente", "detalhe": f"Publicação pendente após falha ({pub['erro']['codigo']}: {pub['erro']['mensagem']}); a entrega está local."}
    return {"estado": "em_andamento", "detalhe": f"Publicação em '{pub['status']}': ainda não conferida na página."}
