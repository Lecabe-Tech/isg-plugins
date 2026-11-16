"""Localizador seguro e somente-leitura de templates por UF/ano e documento orientador."""
from __future__ import annotations

import re
import sys
from pathlib import Path

EQV_SCRIPTS = Path(__file__).resolve().parents[1] / "eqv"
if str(EQV_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(EQV_SCRIPTS))
from isg_eqv.template import TemplateError, read_template

UF_PATTERN = re.compile(r"^[A-Z]{2}$")
ORIENTACAO_EXT = {".pdf", ".docx", ".xlsx"}
ESTADO_EXT = {".pdf", ".docx", ".xlsx", ".doc", ".xls", ".png", ".jpg", ".jpeg"}
MATRIZ_HINT = re.compile(r"matri[zx]|grade|organiza[cç][aã]o.?curricular|carga.?hor[aá]ria", re.I)


def require_folder(location: str | None, variable: str) -> Path:
    if not location or not location.strip():
        raise ValueError(f"{variable}: configure uma pasta local/sincronizada.")
    raw = location.strip()
    if raw.startswith(("http://", "https://")):
        raise ValueError(f"{variable}: URL de pasta requer conector autenticado; use pasta local.")
    path = Path(raw).expanduser()
    if not path.is_absolute():
        raise ValueError(f"{variable}: informe caminho absoluto.")
    path = path.resolve()
    if not path.is_dir():
        raise ValueError(f"{variable}: pasta inacessível.")
    return path


def template_info(location: str | None, uf: str, ano: int) -> dict:
    """Localiza um único template .xlsx e confirma abas EQV + colunas da UF/ano."""
    if not UF_PATTERN.fullmatch(uf or "") or type(ano) is not int or not 2024 <= ano <= 2100:
        raise ValueError("Informe UF (sigla) e ano válido para selecionar o template.")
    root = require_folder(location, "ISG_QUALITY_TEMPLATES_DIR")
    base = root / uf
    if not base.is_dir():
        raise ValueError(f"Template do estado {uf} não encontrado em {root}.")
    places = [base / str(ano), base]
    options: list[Path] = []
    for folder in places:
        if folder.is_dir():
            options = sorted(p for p in folder.glob("*.xlsx") if p.is_file() and not p.name.startswith("~$"))
            if options:
                break
    if not options:
        raise ValueError(f"Template {uf}/{ano}: nenhum XLSX disponível (pode usar {uf}/template.xlsx).")
    if len(options) > 1:
        raise ValueError(f"Template {uf}/{ano}: há {len(options)} XLSX candidatos na mesma pasta; deixe um apenas.")
    path = options[0].resolve()
    if not path.is_relative_to(root):
        raise ValueError("Template não pode apontar para fora da pasta configurada.")
    try:
        parsed = read_template(path)
    except TemplateError as err:
        raise ValueError(f"Template {uf}/{ano} incompatível com EQV: {err.message}") from err
    target = f"{uf}-{ano}"
    missing = [tab for tab in ("1.1", "1.2") if target not in parsed.get("abas", {}).get(tab, {}).get("colunas", {})]
    if missing:
        raise ValueError(f"Template {path.name} não tem a coluna {target} nas abas: {', '.join(missing)}.")
    counts = {tab: len(parsed["abas"][tab]["orientacoes"]) for tab in ("1.1", "1.2")}
    if any(value == 0 for value in counts.values()):
        raise ValueError("Template sem orientações em uma das duas abas da EQV.")
    answers = sum(1 for key in parsed.get("gabarito", {}) if key.endswith(f"|{uf}|{ano}"))
    return {"arquivo": str(path), "sha256": parsed["sha256"], "uf": uf, "ano": ano,
            "orientacoes_por_aba": counts, "respostas_ja_existentes": answers,
            "observacao": "Apenas estrutura e chave de comparação; respostas já existentes NÃO são evidência para novas decisões."}


def resolver_inicio(location_docs: str | None, location_templates: str | None,
                    ano: int, orientacao: str | None, uf: str | None = None) -> dict:
    """Se UF não foi informada, deduz somente pela posição exata UF/Ano do arquivo enviado."""
    if type(ano) is not int or not 2024 <= ano <= 2100:
        raise ValueError("Informe --ano entre 2024 e 2100.")
    docs_root = require_folder(location_docs, "ISG_QUALITY_STATE_DOCS")
    if not orientacao:
        raise ValueError("Informe --orientacao (documento estadual do ciclo).")
    source = Path(orientacao).expanduser()
    if not source.is_absolute() or not source.is_file() or source.suffix.lower() not in ORIENTACAO_EXT:
        raise ValueError("Documento orientador deve ser arquivo existente em caminho absoluto (.pdf/.docx/.xlsx).")
    source = source.resolve()
    if not uf:
        try:
            parts = source.relative_to(docs_root).parts
        except ValueError as e:
            raise ValueError("Documento fora da pasta estadual: informe --uf explicitamente.") from e
        if len(parts) < 3 or not UF_PATTERN.fullmatch(parts[0]) or parts[1] != str(ano):
            raise ValueError("Para inferir UF, o documento deve estar em <documentos>/<UF>/<ANO>/; ou informe --uf.")
        uf = parts[0]
    if not UF_PATTERN.fullmatch(uf):
        raise ValueError("UF deve ter duas letras maiúsculas.")
    state_folder = (docs_root / uf / str(ano)).resolve()
    if not state_folder.is_dir():
        raise ValueError(f"Não existe a pasta de documentos para {uf}/{ano}.")
    if source.is_relative_to(docs_root) and not source.is_relative_to(state_folder):
        raise ValueError(f"Documento orientador não pertence a {uf}/{ano}.")
    files = sorted(p for p in state_folder.rglob("*") if p.is_file() and p.suffix.lower() in ESTADO_EXT)
    template = template_info(location_templates, uf, ano)
    candidates = [str(p.relative_to(state_folder)) for p in files if MATRIZ_HINT.search(p.name)]
    return {"estado": "FONTES_LOCALIZADAS_AGUARDANDO_TRIAGEM_DA_MATRIZ",
            "uf": uf, "ano": ano, "documento_orientador": str(source),
            "template": template, "documentos_na_pasta": [str(p.relative_to(state_folder)) for p in files],
            "possiveis_matrizes_por_nome": candidates,
            "matriz_curricular_confirmada": False,
            "proximos_passos": [
                "Conferir vigência e selecionar a matriz estadual verdadeira (pode estar dentro de um PDF orientador).",
                "Confirmar 7h ou 9h e verificar o referencial ICE aprovado para esse modelo.",
                "Usar o template apenas como contrato de orientações, nunca respostas históricas como evidência.",
                "Executar CFP/SIP/EQV, classificação de componentes e validação JSON antes da importação."
            ]}
