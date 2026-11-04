"""Application-data folder of the plugin (SPEC-003 REQ-COU-01..03).

It lives OUTSIDE the plugin's installed folder, so plugin updates and uninstalls never touch it.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ORG = "InstitutoSonhoGrande"
APP = "isg-model-alignment"

LEIA_ME = """# Pasta de dados do plugin ISG Model Alignment

Esta pasta pertence ao plugin **ISG Model Alignment** do Instituto Sonho Grande.
Ela **não é apagada** quando o plugin é atualizado ou desinstalado.

| Pasta | O que guarda |
|---|---|
| `cfp/` | Documentos PDF já processados (por UF e ano): cópia do original, índice, relatório de qualidade e trechos (chunks) em texto |
| `memoria/` | Cópia local da memória compartilhada do agente (Notion) e feedbacks guardados para envio |
| `config/` | Configurações do usuário |
| `logs/` | Registros de execução |

- É seguro fazer **cópia de segurança** desta pasta.
- Não edite os arquivos à mão: o plugin escreve aqui e confia no que lê.
- Antes de apagar `memoria/outbox/`, confira se não há feedbacks ainda não enviados ao Notion.
- Para apagar tudo, feche o Claude e remova a pasta inteira.
"""


def default_appdata(env=None, platform: str | None = None, home: str | Path | None = None) -> Path:
    env = os.environ if env is None else env
    platform = platform or sys.platform
    home_path = Path(home) if home else Path.home()
    if platform.startswith("win"):
        base = env.get("LOCALAPPDATA") or str(home_path / "AppData" / "Local")
        return Path(base) / ORG / APP
    if platform == "darwin":
        return home_path / "Library" / "Application Support" / ORG / APP
    base = env.get("XDG_DATA_HOME") or str(home_path / ".local" / "share")
    return Path(base) / ORG / APP


def resolve_appdata(override: str | None = None, env=None) -> Path:
    """Override (userConfig data_folder) > ISG_DATA_FOLDER > operating-system default."""
    env = os.environ if env is None else env
    chosen = (override or "").strip() or (env.get("ISG_DATA_FOLDER") or "").strip()
    if chosen:
        return Path(chosen).expanduser()
    return default_appdata(env)


def _inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def ensure_appdata(appdata: Path, plugin_root: Path) -> Path:
    """Creates the folder layout. Refuses a folder inside the plugin's installed folder (REQ-COU-01)."""
    if _inside(appdata, plugin_root):
        raise ValueError("A pasta de dados não pode ficar dentro da pasta instalada do plugin.")
    for sub in ("cfp", "config", "logs", "memoria"):
        (appdata / sub).mkdir(parents=True, exist_ok=True)
    readme = appdata / "LEIA-ME.md"
    if not readme.exists():
        readme.write_text(LEIA_ME, encoding="utf-8", newline="\n")
    return appdata
