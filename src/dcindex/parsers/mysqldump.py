"""A small, tolerant ``mysqldump`` reader: SQL text -> tables of row dicts.

It does not need a MySQL server — it parses ``CREATE TABLE`` (for column order) and ``INSERT INTO``
statements directly. It is deliberately defensive because the Outel DEF CON dumps have quirks:

* INSERTs carry **no column list** (``INSERT INTO `events` VALUES (...)``), so values are mapped
  positionally onto the column order recovered from the matching ``CREATE TABLE``.
* multi-row inserts: ``VALUES (..),(..),(..);``
* standard backslash escaping (``\\n \\t \\' \\" \\\\ \\0``) *and* doubled ``''`` quotes.
* ``NULL`` and numeric literals.

Pure functions, no I/O. ``parse_dump`` returns ``{table_name: ParsedTable}``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Unescape map for backslash escapes inside single-quoted MySQL strings.
_UNESCAPE = {
    "0": "\0", "b": "\b", "n": "\n", "r": "\r", "t": "\t", "Z": "\x1a",
    "\\": "\\", "'": "'", '"': '"', "%": "%", "_": "_",
}

_CREATE_RE = re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?`([^`]+)`\s*\(", re.IGNORECASE)
_INSERT_RE = re.compile(
    r"INSERT\s+(?:IGNORE\s+)?INTO\s+`([^`]+)`\s*(\([^)]*\))?\s*VALUES",
    re.IGNORECASE,
)
_CONSTRAINT_KW = (
    "PRIMARY", "UNIQUE", "KEY", "INDEX", "CONSTRAINT", "FOREIGN", "FULLTEXT", "SPATIAL", "CHECK",
)


@dataclass
class ParsedTable:
    name: str
    columns: list[str] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)


def _matching_paren(text: str, open_idx: int) -> int:
    """Index of the ``)`` matching the ``(`` at ``open_idx`` (string/escape aware)."""
    depth = 0
    i = open_idx
    n = len(text)
    while i < n:
        c = text[i]
        if c == "'":
            _, i = _read_string(text, i)
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return n - 1


def _split_top_level(s: str) -> list[str]:
    """Split on commas not nested in parens and not inside quotes."""
    parts: list[str] = []
    depth = 0
    i = 0
    n = len(s)
    start = 0
    while i < n:
        c = s[i]
        if c == "'":
            _, i = _read_string(s, i)
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif c == "," and depth == 0:
            parts.append(s[start:i])
            start = i + 1
        i += 1
    parts.append(s[start:])
    return parts


def _parse_create_columns(text: str, paren_open: int) -> list[str]:
    close = _matching_paren(text, paren_open)
    body = text[paren_open + 1 : close]
    columns: list[str] = []
    for piece in _split_top_level(body):
        piece = piece.strip()
        if not piece:
            continue
        if piece.startswith("`"):
            end = piece.find("`", 1)
            if end > 1:
                columns.append(piece[1:end])
        # else: a constraint/key line (PRIMARY KEY, etc.) — not a column
        elif piece.split(None, 1)[0].upper() not in _CONSTRAINT_KW:
            # Unbackticked column name (rare) — take the leading identifier.
            m = re.match(r"([A-Za-z_][A-Za-z0-9_]*)", piece)
            if m:
                columns.append(m.group(1))
    return columns


def _read_string(text: str, i: int) -> tuple[str, int]:
    """Read a single-quoted string starting at ``text[i] == \"'\"``. Returns (value, next_index)."""
    assert text[i] == "'"
    i += 1
    out: list[str] = []
    n = len(text)
    while i < n:
        c = text[i]
        if c == "\\":
            nxt = text[i + 1] if i + 1 < n else ""
            out.append(_UNESCAPE.get(nxt, nxt))
            i += 2
            continue
        if c == "'":
            if i + 1 < n and text[i + 1] == "'":  # doubled quote -> literal '
                out.append("'")
                i += 2
                continue
            i += 1
            break
        out.append(c)
        i += 1
    return "".join(out), i


def _coerce_token(token: str):
    t = token.strip()
    if not t:
        return None
    up = t.upper()
    if up == "NULL":
        return None
    if up == "TRUE":
        return 1
    if up == "FALSE":
        return 0
    if re.fullmatch(r"[-+]?\d+", t):
        try:
            return int(t)
        except ValueError:
            return t
    if re.fullmatch(r"[-+]?\d*\.\d+(?:[eE][-+]?\d+)?", t):
        try:
            return float(t)
        except ValueError:
            return t
    return t


def _read_value(text: str, i: int):
    if text[i] == "'":
        return _read_string(text, i)
    j = i
    n = len(text)
    while j < n and text[j] not in ",)":
        j += 1
    return _coerce_token(text[i:j]), j


def _parse_values(text: str, start: int) -> tuple[list[list], int]:
    """Parse the ``(..),(..);`` tuple list beginning at ``start`` (just after VALUES)."""
    rows: list[list] = []
    i = start
    n = len(text)
    while i < n:
        while i < n and text[i] in " \t\r\n,":
            i += 1
        if i >= n or text[i] == ";":
            i += 1
            break
        if text[i] != "(":
            break
        i += 1  # past '('
        values: list = []
        while i < n:
            while i < n and text[i] in " \t\r\n":
                i += 1
            if i >= n:
                break
            if text[i] == ")":
                i += 1
                break
            if text[i] == ",":
                i += 1
                continue
            value, i = _read_value(text, i)
            values.append(value)
        rows.append(values)
    return rows, i


def _parse_insert_column_list(group: str | None) -> list[str] | None:
    if not group:
        return None
    inner = group.strip()[1:-1]  # drop ( )
    cols = [c.strip().strip("`") for c in inner.split(",")]
    return [c for c in cols if c]


def parse_dump(text: str) -> dict[str, ParsedTable]:
    """Parse mysqldump SQL into ``{table_name: ParsedTable}`` (keyed by lowercase table name)."""
    tables: dict[str, ParsedTable] = {}

    # First pass: column order from CREATE TABLE.
    for m in _CREATE_RE.finditer(text):
        name = m.group(1)
        key = name.lower()
        cols = _parse_create_columns(text, m.end() - 1)  # m.end()-1 points at the '('
        tables[key] = ParsedTable(name=name, columns=cols)

    # Second pass: rows from INSERT statements.
    for m in _INSERT_RE.finditer(text):
        name = m.group(1)
        key = name.lower()
        table = tables.setdefault(key, ParsedTable(name=name))
        insert_cols = _parse_insert_column_list(m.group(2))
        columns = insert_cols or table.columns
        value_rows, _ = _parse_values(text, m.end())
        for values in value_rows:
            if columns:
                row = {col: (values[idx] if idx < len(values) else None) for idx, col in enumerate(columns)}
            else:
                row = {str(idx): v for idx, v in enumerate(values)}
            table.rows.append(row)

    return tables
