#!/usr/bin/env python3
"""PostToolUse(Edit|Write): no TODOs in source (wiki/dogmas.md). Exit 2 feeds stderr back."""

import json
import pathlib
import re
import sys

SOURCE = {".py", ".ts", ".svelte", ".html", ".css", ".js"}
MARKER = re.compile(r"\b(TODO|FIXME|XXX)\b")

try:
    path = pathlib.Path(json.load(sys.stdin)["tool_input"]["file_path"])
except (KeyError, TypeError, ValueError):
    sys.exit(0)

blocking = []
if path.suffix in SOURCE and path.is_file() and path.resolve().is_relative_to(pathlib.Path.cwd()):
    lines = enumerate(path.read_text().splitlines(), 1)
    hits = [f"{path}:{n}" for n, line in lines if MARKER.search(line)]
    if hits:
        blocking.append(
            "No TODOs (wiki/dogmas.md#code): do the work now, or run it through /intake onto "
            "BOARD.md. Remove: " + ", ".join(hits[:5])
        )
if blocking:
    print("\n".join(blocking), file=sys.stderr)
    sys.exit(2)
