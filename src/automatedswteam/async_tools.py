"""
Module: async_tools.py
Purpose: Asynchronous path-sandboxed file, index, and shell execution tools.
Owner: Tooling Architect
Depends on: tools
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Literal

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from .tools import (
    CodeNode,
    _CODE_SUFFIXES,
    _CMD_TIMEOUT_SEC,
    _MAX_CMD_CHARS,
    _MAX_FILE_CHARS,
    _ROLE_CWD,
    _assert_allowed,
    _header_warning,
    _resolve_in_workspace,
    file_header,
    get_workspace_root,
    load_codemap,
    normalize_tree_path,
    posix_rel,
    write_codemap,
)

logger = logging.getLogger(__name__)

Role = Literal["frontend", "backend", "qa"]


def make_async_agent_tools(role: Role) -> tuple[list[BaseTool], dict[str, BaseTool]]:
    """Build path-sandboxed async-native tools for an implementer role."""

    async def read_file(path: str) -> str:
        """Read a UTF-8 text file relative to the workspace root."""
        resolved = _resolve_in_workspace(path)
        _assert_allowed(role, resolved, write=False)
        if not resolved.is_file():
            return f"ERROR: file not found: {posix_rel(str(resolved.relative_to(get_workspace_root().resolve())))}"
        
        # Offload file read to thread pool to avoid blocking the loop
        text = await asyncio.to_thread(resolved.read_text, encoding="utf-8")
        if len(text) > _MAX_FILE_CHARS:
            return text[:_MAX_FILE_CHARS] + "\n... [truncated]"
        return text

    async def write_file(path: str, content: str) -> str:
        """Create or overwrite a UTF-8 text file asynchronously inside your owned folder."""
        resolved = _resolve_in_workspace(path)
        _assert_allowed(role, resolved, write=True)
        
        def _write():
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(content, encoding="utf-8")

        await asyncio.to_thread(_write)
        rel = posix_rel(str(resolved.relative_to(get_workspace_root().resolve())))
        warning = _header_warning(resolved, content)
        return f"Wrote {rel} ({len(content)} chars).{warning}"

    async def list_dir(path: str = ".") -> str:
        """List files and folders under a workspace-relative path asynchronously."""
        resolved = _resolve_in_workspace(path)
        _assert_allowed(role, resolved, write=False)
        if not resolved.exists():
            return f"ERROR: path not found: {path}"
        if resolved.is_file():
            return posix_rel(str(resolved.relative_to(get_workspace_root().resolve())))
        
        def _list():
            entries = []
            for child in sorted(resolved.iterdir()):
                mark = "/" if child.is_dir() else ""
                entries.append(posix_rel(str(child.relative_to(get_workspace_root().resolve()))) + mark)
            return "\n".join(entries) if entries else "(empty directory)"

        return await asyncio.to_thread(_list)

    async def lookup_code_index(query: str, folder: str = "") -> str:
        """Search CODEMAP for modular files asynchronously."""
        payload = await asyncio.to_thread(load_codemap)
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

    async def update_codemap_entry(path: str, purpose: str, exports: str = "", depends_on: str = "") -> str:
        """Add or update a CODEMAP entry asynchronously."""
        rel = posix_rel(path)
        resolved = _resolve_in_workspace(rel)
        _assert_allowed(role, resolved, write=True)
        if role == "qa":
            return "ERROR: QA does not own CODEMAP application entries."
        if not rel.startswith(f"{role}/"):
            rel = normalize_tree_path(rel, role)

        def _update():
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
            return updated

        updated = await asyncio.to_thread(_update)
        action = "Updated" if updated else "Added"
        return f"{action} CODEMAP entry for {rel}."

    async def run_command(command: str) -> str:
        """Run a shell command asynchronously with non-blocking process management."""
        command = (command or "").strip()
        if not command:
            return "ERROR: empty command."
        if ".." in command:
            return "ERROR: command may not contain '..'."
        cwd = get_workspace_root() / _ROLE_CWD[role]
        cwd.mkdir(parents=True, exist_ok=True)

        try:
            # Use non-blocking async subprocess creation
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            # Wait for execution with timeout
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=_CMD_TIMEOUT_SEC
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            return f"ERROR: command timed out after {_CMD_TIMEOUT_SEC}s: {command}"

        output = (stdout.decode("utf-8", errors="replace")) + (stderr.decode("utf-8", errors="replace"))
        if len(output) > _MAX_CMD_CHARS:
            output = output[:_MAX_CMD_CHARS] + "\n... [truncated]"
        return f"exit={proc.returncode} cwd={cwd}\n{output}".rstrip()

    tools = [
        StructuredTool.from_function(name="read_file", coroutine=read_file),
        StructuredTool.from_function(name="write_file", coroutine=write_file),
        StructuredTool.from_function(name="list_dir", coroutine=list_dir),
        StructuredTool.from_function(name="lookup_code_index", coroutine=lookup_code_index),
        StructuredTool.from_function(name="update_codemap_entry", coroutine=update_codemap_entry),
        StructuredTool.from_function(name="run_command", coroutine=run_command),
    ]
    return tools, {tool.name: tool for tool in tools}