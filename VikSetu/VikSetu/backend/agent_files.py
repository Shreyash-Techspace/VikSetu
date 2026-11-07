"""Workspace file tools for the canvas agent (read, hex, parse, list)."""
from __future__ import annotations

import csv
import json
import mimetypes
import re
from io import StringIO
from pathlib import Path

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
TEXT_SUFFIXES = {".txt", ".md", ".csv", ".json", ".geojson", ".xml", ".html", ".htm", ".log"}


def safe_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", Path(name).name).strip("._")
    return (cleaned or "file")[:80]


def file_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return "image"
    if suffix in TEXT_SUFFIXES:
        return "text"
    return "binary"


def _is_under(root: Path, target: Path) -> bool:
    try:
        target.relative_to(root)
        return True
    except ValueError:
        return False


def resolve_path(work: Path, inbox: Path, action: dict) -> Path:
    file_id = action.get("fileId") or action.get("file_id")
    rel = action.get("path") or action.get("file") or ""
    if file_id:
        name = safe_name(str(file_id))
        candidate = (inbox / name).resolve()
        if candidate.is_file() and _is_under(inbox.resolve(), candidate):
            return candidate
        candidate = (work / name).resolve()
        if candidate.is_file() and _is_under(work.resolve(), candidate):
            return candidate
        under = (work / "inbox" / name).resolve()
        if under.is_file() and _is_under(work.resolve(), under):
            return under
        raise FileNotFoundError(f"Unknown fileId: {file_id}")
    rel_text = str(rel).replace("\\", "/").strip().lstrip("/")
    if not rel_text or rel_text in {".", "./"}:
        target = work.resolve()
    else:
        target = (work / rel_text).resolve()
    root = work.resolve()
    if not _is_under(root, target):
        raise PermissionError("Path must stay inside agent_workspace.")
    if not target.exists():
        raise FileNotFoundError(f"No such path: {rel_text or '.'}")
    return target


def run_file_action(work: Path, inbox: Path, action: dict) -> dict:
    mode = str(action.get("mode") or action.get("tool") or "text").strip().lower()
    op = str(action.get("op") or "file-read")
    try:
        if op == "file-list" or mode == "list":
            rel = str(action.get("path") or action.get("dir") or "").strip()
            target = resolve_path(work, inbox, {"path": rel or "."})
            if not target.is_dir():
                return {"ok": False, "error": "Not a directory.", "mode": "list"}
            entries = []
            for child in sorted(target.iterdir(), key=lambda p: p.name.lower())[:200]:
                if child.name == "_last_script.py":
                    continue
                stat = child.stat()
                entries.append(
                    {
                        "name": child.name,
                        "path": child.relative_to(work).as_posix(),
                        "dir": child.is_dir(),
                        "bytes": stat.st_size if child.is_file() else None,
                        "kind": file_kind(child) if child.is_file() else "dir",
                    }
                )
            return {"ok": True, "mode": "list", "path": target.relative_to(work).as_posix(), "entries": entries}

        path = resolve_path(work, inbox, action)
        if path.is_dir():
            return {"ok": False, "error": "Expected a file; use mode list for directories.", "path": path.name}

        offset = max(0, int(action.get("offset") or 0))
        length = int(action.get("length") or action.get("max_bytes") or 4096)
        length = max(16, min(length, 65536))
        max_chars = int(action.get("max_chars") or 12000)
        max_chars = max(200, min(max_chars, 50000))
        raw = path.read_bytes()
        slice_raw = raw[offset : offset + length]
        mime, _ = mimetypes.guess_type(path.name)
        meta = {
            "path": path.relative_to(work).as_posix(),
            "bytes": len(raw),
            "kind": file_kind(path),
            "mime": mime or "application/octet-stream",
            "suffix": path.suffix.lower(),
        }

        if mode == "meta":
            return {"ok": True, "mode": "meta", **meta}

        if mode == "hex":
            lines = []
            chunk = slice_raw[: min(len(slice_raw), 512)]
            for index in range(0, len(chunk), 16):
                row = chunk[index : index + 16]
                hex_part = " ".join(f"{byte:02x}" for byte in row)
                ascii_part = "".join(chr(byte) if 32 <= byte < 127 else "." for byte in row)
                lines.append(f"{offset + index:08x}  {hex_part:<47}  {ascii_part}")
            return {
                "ok": True,
                "mode": "hex",
                **meta,
                "offset": offset,
                "shown_bytes": len(chunk),
                "dump": "\n".join(lines),
            }

        if mode == "parse":
            text = raw.decode("utf-8", errors="replace")
            suffix = path.suffix.lower()
            if suffix == ".json" or text.lstrip().startswith(("{", "[")):
                try:
                    parsed = json.loads(text)
                    preview = json.dumps(parsed, ensure_ascii=False)[:max_chars]
                    return {"ok": True, "mode": "parse", "format": "json", **meta, "preview": preview}
                except json.JSONDecodeError as exc:
                    return {"ok": False, "mode": "parse", "error": str(exc), **meta}
            if suffix == ".csv":
                reader = csv.reader(StringIO(text))
                rows = []
                for row_index, row in enumerate(reader):
                    if row_index >= 40:
                        break
                    rows.append(row)
                return {"ok": True, "mode": "parse", "format": "csv", **meta, "rows": rows}
            return {
                "ok": True,
                "mode": "parse",
                "format": "text",
                **meta,
                "preview": text[:max_chars],
            }

        # default: text
        text = slice_raw.decode("utf-8", errors="replace")
        if offset == 0 and len(raw) <= max_chars:
            body = raw.decode("utf-8", errors="replace")
        else:
            body = text[:max_chars]
        return {
            "ok": True,
            "mode": "text",
            **meta,
            "offset": offset,
            "truncated": len(body) >= max_chars or offset + len(slice_raw) < len(raw),
            "text": body,
        }
    except (FileNotFoundError, PermissionError, ValueError) as exc:
        return {"ok": False, "mode": mode, "error": str(exc), "op": op}
