"""SharePoint links as informed locations (decision of 2026-11-17, after the MG pilot).

Requesters often send a SharePoint link instead of the file. A SharePoint link is NOT a web search: it points to a file or
folder of the Institute's own document libraries, so it is accepted as an input. The program still never goes to the
network. It maps the link to the copy that the OneDrive client keeps on this computer:
  * a library synced with "Sincronizar" is registered by the OneDrive client (Windows registry
    HKCU\\Software\\SyncEngines\\Providers\\OneDrive: UrlNamespace -> MountPoint), so the link path maps to a local path;
  * a folder added with "Adicionar atalho a Meus arquivos" appears inside the OneDrive folder; it is found by the end of
    the link path (folder + file name) under each OneDrive folder;
  * the analyst may also give the copy explicitly (`copia_local` in the manifest), for example a downloaded file.
When no copy is found the input becomes a pending item that says what to do. The SharePoint connector of Claude is used
only to identify the file (name, folder, last change); its text is not evidence, because it has no page, cell or
position that the program can check. Standard library only.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

SP_HOST = re.compile(r"(^|\.)sharepoint\.com$", re.I)
SHARING = re.compile(r"^/:[a-z]+:/[a-z]/", re.I)  # /:x:/s/Site/<token>, /:b:/g/...: opaque sharing token
PATH_LINK = re.compile(r"^/:[a-z]+:/r(/.*)$", re.I)  # /:x:/r/sites/Site/Library/folder/file.xlsx


def is_sharepoint(uri: str) -> bool:
    p = urlparse(uri or "")
    return p.scheme.lower() == "https" and bool(SP_HOST.search(p.hostname or ""))


def parse_link(url: str) -> dict:
    """{'host', 'tipo': 'caminho'|'compartilhamento'|'documento', 'caminho': server-relative path or None,
    'nome': file name or None, 'segmentos': path segments}."""
    p = urlparse(url)
    path = unquote(p.path)
    q = parse_qs(p.query)
    out = {"host": (p.hostname or "").lower(), "tipo": "caminho", "caminho": None, "nome": None, "segmentos": []}
    m = PATH_LINK.match(path)
    if m:
        path = m.group(1)
    if SHARING.match(path):
        out["tipo"] = "compartilhamento"
    elif "/_layouts/" in path.lower() or path.lower().endswith("/allitems.aspx"):
        ident = (q.get("id") or [""])[0]
        if ident.startswith("/"):
            out["caminho"] = ident
        else:
            out["tipo"] = "documento"
            out["nome"] = (q.get("file") or [None])[0]
    else:
        out["caminho"] = path
    if out["caminho"]:
        segs = [s for s in out["caminho"].split("/") if s]
        out["segmentos"] = segs
        if segs and Path(segs[-1]).suffix:
            out["nome"] = segs[-1]
    return out


def synced_libraries() -> list:
    """[(url_namespace, mount_point)] of the libraries synced by the OneDrive client on this computer (Windows)."""
    out = []
    if sys.platform != "win32":
        return out
    try:
        import winreg

        base = r"Software\SyncEngines\Providers\OneDrive"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, base) as root:
            i = 0
            while True:
                try:
                    name = winreg.EnumKey(root, i)
                except OSError:
                    break
                i += 1
                try:
                    with winreg.OpenKey(root, name) as k:
                        url = winreg.QueryValueEx(k, "UrlNamespace")[0]
                        mount = winreg.QueryValueEx(k, "MountPoint")[0]
                    if url and mount:
                        out.append((url, mount))
                except OSError:
                    continue
    except (ImportError, OSError):
        return []
    return out


def onedrive_folders(libraries: list) -> list:
    """Local OneDrive folders where shortcuts may live: mount points plus the OneDrive environment folders."""
    seen, out = set(), []
    cands = [m for _, m in libraries] + [os.environ.get(v) for v in ("OneDriveCommercial", "OneDrive")]
    home = Path.home() / "Library" / "CloudStorage"  # macOS
    if home.is_dir():
        cands += [str(p) for p in home.iterdir() if p.is_dir() and p.name.lower().startswith(("onedrive", "sharepoint"))]
    for c in cands:
        if c and Path(c).is_dir() and str(Path(c)).lower() not in seen:
            seen.add(str(Path(c)).lower())
            out.append(Path(c))
    return out


def _norm(s: str) -> str:
    return unquote(s).replace("\\", "/").rstrip("/").lower()


def local_copy(url: str, libraries: list | None = None, folders: list | None = None) -> dict:
    """{'caminho': Path|None, 'metodo': 'biblioteca_sincronizada'|'atalho_onedrive'|None, 'link': parse_link(url), 'motivo'}."""
    link = parse_link(url)
    libs = synced_libraries() if libraries is None else libraries
    out = {"caminho": None, "metodo": None, "link": link, "motivo": ""}
    if link["tipo"] != "caminho":
        out["motivo"] = ("link de compartilhamento sem o caminho do arquivo" if link["tipo"] == "compartilhamento"
                         else "link de visualização sem o caminho do arquivo") + \
                        ("" if not link["nome"] else f" (arquivo {link['nome']})")
        return out
    full = _norm(link["caminho"])
    for ns, mount in libs:
        nsp = urlparse(ns)
        if (nsp.hostname or "").lower() != link["host"]:
            continue
        prefix = _norm(nsp.path)
        if full == prefix or full.startswith(prefix + "/"):
            rest = [s for s in unquote(link["caminho"]).split("/") if s][len([s for s in prefix.split("/") if s]):]
            cand = Path(mount).joinpath(*rest)
            if cand.exists():
                out.update(caminho=cand, metodo="biblioteca_sincronizada")
                return out
    segs = link["segmentos"]
    roots = onedrive_folders(libs) if folders is None else [Path(f) for f in folders]
    for k in range(len(segs) - 1, 1, -1):  # longest end of the path first; at least one folder + the item
        hits = {str(r.joinpath(*segs[-k:])) for r in roots if r.joinpath(*segs[-k:]).exists()}
        if len(hits) == 1:
            out.update(caminho=Path(hits.pop()), metodo="atalho_onedrive")
            return out
        if len(hits) > 1:
            out["motivo"] = "mais de uma cópia local possível: " + "; ".join(sorted(hits))
            return out
    out["motivo"] = "a biblioteca do SharePoint não está sincronizada neste computador"
    return out


def missing_message(url: str, motivo: str) -> str:
    return (f"Link do SharePoint sem cópia neste computador ({motivo}): {url}. Sincronize a biblioteca no OneDrive "
            "(botão Sincronizar ou 'Adicionar atalho a Meus arquivos') ou baixe o arquivo e informe o caminho em "
            "copia_local no manifesto. O programa não baixa documentos.")
