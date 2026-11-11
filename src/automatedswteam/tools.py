"""Sandboxed file, index, and shell tools for implementer agents."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Literal

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

Role = Literal["frontend", "backend", "qa"]

_CODEMAP_JSON = "CODEMAP.json"
_CODEMAP_MD = "CODEMAP.md"
_CONTRACTS_DIR = "contracts"
_CODE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".css"}
_MAX_FILE_CHARS = 40_000
_MAX_CMD_CHARS = 8_000
_CMD_TIMEOUT_SEC = 60

_workspace_root: Path | None = None

_ROLE_WRITE_DIRS: dict[str, tuple[str, ...]] = {
    "frontend": ("frontend",),
    "backend": ("backend", "contracts"),
    "qa": ("qa",),
}

_ROLE_READ_DIRS: dict[str, tuple[str, ...]] = {
    "frontend": ("frontend", "backend", "contracts", "qa"),
    "backend": ("frontend", "backend", "contracts", "qa"),
    "qa": ("frontend", "backend", "contracts", "qa"),
}

_ROLE_CWD: dict[str, str] = {
    "frontend": "frontend",
    "backend": "backend",
    "qa": "qa",
}


class CodeNode(BaseModel):
    path: str = Field(description="Workspace-relative path, e.g. frontend/src/App.tsx")
    purpose: str = Field(description="One-line description of this file's responsibility")
    exports: str = Field(default="", description="Public functions, components, classes, or types")
    depends_on: str = Field(default="", description="Other CODEMAP paths or API contracts this file uses")


def get_workspace_root() -> Path:
    if _workspace_root is not None:
        return _workspace_root
    return Path.cwd() / "workspace"


def set_workspace_root(path: Path) -> Path:
    global _workspace_root
    resolved = path.resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    _workspace_root = resolved
    return resolved


def posix_rel(path: str) -> str:
    return path.replace("\\", "/").lstrip("/")


def normalize_tree_path(path: str, owner: str) -> str:
    rel = posix_rel(path)
    if rel.startswith("contracts/"):
        return rel
    prefix = f"{owner}/"
    if rel.startswith(("frontend/", "backend/", "qa/")):
        if not rel.startswith(prefix):
            return prefix + rel.split("/", 1)[-1]
        return rel
    return prefix + rel


def file_header(rel_path: str, purpose: str, owner: str, depends_on: str = "") -> str:
    suffix = Path(rel_path).suffix.lower()
    if suffix == ".py":
        return (
            '"""\n'
            f"Module: {rel_path}\n"
            f"Purpose: {purpose}\n"
            f"Owner: {owner}\n"
            f"Depends on: {depends_on or 'none'}\n"
            '"""\n\n'
        )
    if suffix in {".ts", ".tsx", ".js", ".jsx", ".css"}:
        return (
            "/**\n"
            f" * Module: {rel_path}\n"
            f" * Purpose: {purpose}\n"
            f" * Owner: {owner}\n"
            f" * Depends on: {depends_on or 'none'}\n"
            " */\n\n"
        )
    return (
        f"# Module: {rel_path}\n"
        f"# Purpose: {purpose}\n"
        f"# Owner: {owner}\n"
        f"# Depends on: {depends_on or 'none'}\n\n"
    )


def stub_content(rel_path: str, purpose: str, owner: str, depends_on: str = "") -> str:
    header = file_header(rel_path, purpose, owner, depends_on)
    suffix = Path(rel_path).suffix.lower()
    if suffix == ".py":
        return header + "# TODO: implement\n"
    if suffix in {".ts", ".tsx", ".js", ".jsx"}:
        return header + "// TODO: implement\n"
    return header


def render_codemap_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# CODEMAP: {payload.get('app_name', 'app')}",
        "",
        payload.get("summary", ""),
        "",
        "Use this index to find the file that owns a feature before reading or editing.",
        "",
    ]
    for folder in ("frontend", "backend"):
        lines.append(f"## {folder}")
        nodes = payload.get(folder) or []
        if not nodes:
            lines.append("- (empty)")
            lines.append("")
            continue
        for node in sorted(nodes, key=lambda n: n.get("path", "")):
            path = node.get("path", "")
            purpose = node.get("purpose", "")
            lines.append(f"- `{path}` — {purpose}")
            if node.get("exports"):
                lines.append(f"  - exports: {node['exports']}")
            if node.get("depends_on"):
                lines.append(f"  - depends_on: {node['depends_on']}")
        lines.append("")
    contracts = (payload.get("contracts") or "").strip()
    if contracts:
        lines.extend(["## contracts", "", contracts, ""])
    return "\n".join(lines).rstrip() + "\n"


def write_codemap(payload: dict[str, Any]) -> Path:
    root = get_workspace_root()
    json_path = root / _CODEMAP_JSON
    md_path = root / _CODEMAP_MD
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_path.write_text(render_codemap_markdown(payload), encoding="utf-8")
    return md_path


def load_codemap() -> dict[str, Any]:
    path = get_workspace_root() / _CODEMAP_JSON
    if not path.exists():
        return {"app_name": "", "summary": "", "contracts": "", "frontend": [], "backend": []}
    return json.loads(path.read_text(encoding="utf-8"))


def scaffold_workspace(
    app_name: str,
    summary: str,
    contracts: str,
    frontend_tree: list[CodeNode],
    backend_tree: list[CodeNode],
) -> Path:
    root = set_workspace_root(Path.cwd() / "workspace")
    for folder in ("frontend", "backend", "qa", _CONTRACTS_DIR):
        (root / folder).mkdir(parents=True, exist_ok=True)

    payload = {
        "app_name": app_name,
        "summary": summary,
        "contracts": contracts,
        "frontend": [node.model_dump() for node in frontend_tree],
        "backend": [node.model_dump() for node in backend_tree],
    }
    for node in payload["frontend"]:
        node["path"] = normalize_tree_path(node["path"], "frontend")
    for node in payload["backend"]:
        node["path"] = normalize_tree_path(node["path"], "backend")

    write_codemap(payload)
    (root / _CONTRACTS_DIR / "api.md").write_text(
        file_header(f"{_CONTRACTS_DIR}/api.md", "Shared API contracts", "lead", "CODEMAP")
        + (contracts or "# No contracts specified.\n"),
        encoding="utf-8",
    )

    for owner, nodes in (("frontend", payload["frontend"]), ("backend", payload["backend"])):
        for node in nodes:
            rel = node.get("path", "")

            # Skip paths containing wildcards or illegal Windows filename characters
            if any(char in rel for char in ['*', '?', '<', '>', ':', '"', '|']):
                continue
            dest = root / Path(rel)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists() and dest.stat().st_size > 0:
                continue
            dest.write_text(
                stub_content(rel, node.get("purpose", ""), owner, node.get("depends_on", "")),
                encoding="utf-8",
            )
    return root


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _resolve_in_workspace(path: str) -> Path:
    root = get_workspace_root().resolve()
    raw = Path(posix_rel(path))
    candidate = raw.resolve() if raw.is_absolute() else (root / raw).resolve()
    if not _is_relative_to(candidate, root):
        raise ValueError(f"Path '{path}' is outside the workspace.")
    return candidate


def _allowed_dir_roots(role: str, write: bool) -> list[Path]:
    root = get_workspace_root().resolve()
    names = _ROLE_WRITE_DIRS[role] if write else _ROLE_READ_DIRS[role]
    return [root / name for name in names]


def _assert_allowed(role: str, resolved: Path, write: bool) -> None:
    workspace = get_workspace_root().resolve()
    if not write and resolved in {workspace, workspace / _CODEMAP_JSON, workspace / _CODEMAP_MD}:
        return
    roots = _allowed_dir_roots(role, write)
    if any(resolved == folder or _is_relative_to(resolved, folder) for folder in roots):
        return
    action = "write" if write else "read"
    allowed = ", ".join(str(p) for p in roots)
    raise PermissionError(f"{role} agent cannot {action} '{resolved}'. Allowed: {allowed}")


def _header_warning(path: Path, content: str) -> str:
    if path.suffix.lower() not in _CODE_SUFFIXES:
        return ""
    head = content[:1200].lower()
    if "module:" in head and "purpose:" in head:
        return ""
    return (
        " WARNING: missing top-of-file header with Module, Purpose, Owner, and Depends on."
    )


def make_agent_tools(role: Role) -> tuple[list[BaseTool], dict[str, BaseTool]]:
    """Build path-sandboxed tools for one implementer role."""

    def read_file(path: str) -> str:
        """Read a UTF-8 text file relative to the workspace root (CODEMAP, contracts, or either app folder)."""
        resolved = _resolve_in_workspace(path)
        _assert_allowed(role, resolved, write=False)
        if not resolved.is_file():
            return f"ERROR: file not found: {posix_rel(str(resolved.relative_to(get_workspace_root().resolve())))}"
        text = resolved.read_text(encoding="utf-8")
        if len(text) > _MAX_FILE_CHARS:
            return text[:_MAX_FILE_CHARS] + "\n... [truncated]"
        return text

    def write_file(path: str, content: str) -> str:
        """Create or overwrite a UTF-8 text file. You may only write inside your owned folder. Include a file header and function docstrings."""
        resolved = _resolve_in_workspace(path)
        _assert_allowed(role, resolved, write=True)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        rel = posix_rel(str(resolved.relative_to(get_workspace_root().resolve())))
        warning = _header_warning(resolved, content)
        return f"Wrote {rel} ({len(content)} chars).{warning}"

    def list_dir(path: str = ".") -> str:
        """List files and folders under a workspace-relative path."""
        resolved = _resolve_in_workspace(path)
        _assert_allowed(role, resolved, write=False)
        if not resolved.exists():
            return f"ERROR: path not found: {path}"
        if resolved.is_file():
            return posix_rel(str(resolved.relative_to(get_workspace_root().resolve())))
        entries = []
        for child in sorted(resolved.iterdir()):
            mark = "/" if child.is_dir() else ""
            entries.append(posix_rel(str(child.relative_to(get_workspace_root().resolve()))) + mark)
        return "\n".join(entries) if entries else "(empty directory)"

    def lookup_code_index(query: str, folder: str = "") -> str:
        """Search CODEMAP for modular files. folder is frontend, backend, or empty for both. Call this before editing."""
        # Normalize invalid model inputs like "all", "none", "root"
        if folder not in ("frontend", "backend", ""):
            folder = ""
        payload = load_codemap()
        needle = (query or "").strip().lower()
        folder_key = folder.strip().lower()
        if folder_key and folder_key not in {"frontend", "backend"}:
            return "ERROR: folder must be 'frontend', 'backend', or empty."
        sections = [folder_key] if folder_key else ["frontend", "backend"]
        hits: list[str] = []
        for section in sections:
            for node in payload.get(section) or []:
                blob = " ".join(
                    str(node.get(k, "")) for k in ("path", "purpose", "exports", "depends_on")
                ).lower()
                if needle and needle not in blob:
                    continue
                hits.append(
                    f"- `{node.get('path')}` — {node.get('purpose')}\n"
                    f"  exports: {node.get('exports') or '(none)'}\n"
                    f"  depends_on: {node.get('depends_on') or '(none)'}"
                )
        if not hits:
            return f"No CODEMAP matches for query={query!r} folder={folder or 'all'}."
        return "\n".join(hits)

    def update_codemap_entry(path: str, purpose: str, exports: str = "", depends_on: str = "") -> str:
        """Add or update a CODEMAP entry for a file you own. Keep the index in sync when you add modules."""
        rel = posix_rel(path)
        resolved = _resolve_in_workspace(rel)
        _assert_allowed(role, resolved, write=True)
        if role == "qa":
            return "ERROR: QA does not own CODEMAP application entries."
        if not rel.startswith(f"{role}/"):
            rel = normalize_tree_path(rel, role)
        payload = load_codemap()
        nodes = payload.setdefault(role, [])
        updated = False
        for node in nodes:
            if posix_rel(node.get("path", "")) == rel:
                node["purpose"] = purpose
                node["exports"] = exports
                node["depends_on"] = depends_on
                updated = True
                break
        if not updated:
            nodes.append(
                {"path": rel, "purpose": purpose, "exports": exports, "depends_on": depends_on}
            )
        write_codemap(payload)
        action = "Updated" if updated else "Added"
        return f"{action} CODEMAP entry for {rel}."

    def run_command(command: str) -> str:
        """Run a shell command with cwd locked to this agent's folder (frontend, backend, or qa)."""
        command = (command or "").strip()
        if not command:
            return "ERROR: empty command."
        if ".." in command:
            return "ERROR: command may not contain '..'."
        cwd = get_workspace_root() / _ROLE_CWD[role]
        cwd.mkdir(parents=True, exist_ok=True)
        try:
            completed = subprocess.run(
                command,
                cwd=str(cwd),
                shell=True,
                capture_output=True,
                text=True,
                timeout=_CMD_TIMEOUT_SEC,
            )
        except subprocess.TimeoutExpired:
            return f"ERROR: command timed out after {_CMD_TIMEOUT_SEC}s: {command}"
        output = (completed.stdout or "") + (completed.stderr or "")
        if len(output) > _MAX_CMD_CHARS:
            output = output[:_MAX_CMD_CHARS] + "\n... [truncated]"
        return f"exit={completed.returncode} cwd={cwd}\n{output}".rstrip()

    tools = [
        StructuredTool.from_function(name="read_file", func=read_file),
        StructuredTool.from_function(name="write_file", func=write_file),
        StructuredTool.from_function(name="list_dir", func=list_dir),
        StructuredTool.from_function(name="lookup_code_index", func=lookup_code_index),
        StructuredTool.from_function(name="update_codemap_entry", func=update_codemap_entry),
        StructuredTool.from_function(name="run_command", func=run_command),
    ]
    return tools, {tool.name: tool for tool in tools}
