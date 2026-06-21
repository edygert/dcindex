# dcindex

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)

Local-first indexer for **DEF CON** conference schedule metadata. It ingests structured session data
from the **"Outel" MySQL schedule dumps**, stores it in a local SQLite database, and gives you
full-text search over talks, villages, demo labs, workshops, trainings, and contests — **metadata
only; it never downloads presentation files, videos, or other assets.** Material/video/forum URLs are
recorded and displayed so you can open them yourself.

This is **Phase 1 (backend + CLI)**. The service layer is FastAPI-friendly so a TUI or web layer can
wrap the same operations later.

## Data source

DEF CON schedules are republished in many formats by the unofficial **"The One!"** project at
[`defcon.outel.org`](https://defcon.outel.org). Among them is a **MySQL dump** per year:

```
https://defcon.outel.org/defcon<NN>/dc<NN>_mysqldump.txt
```

Dumps are available for **DC26–DC33 (2018–2025)**. These files are unofficial ("not affiliated with
DEF CON … use at your own risk") and carry no stated license or redistribution restriction. dcindex
indexes the **metadata only** and links back to original sources — it does not rebundle the dataset.
Please respect the source site and be considerate (dcindex paces and caches its single network call).

## How it works

- **`ingest-dump`** reads a local dump file (offline). It parses the `mysqldump` SQL directly — no
  MySQL server needed.
- **`ingest-url`** fetches a published dump **once**, saves it to a local cache
  (`<data_dir>/dumps/`), and ingests the cached copy. Re-running ingests from cache with **no network
  call** (`--refresh` forces a re-download).
- The dumps' core (`events` = talks, `speakers`) is stable across all years; auxiliary activity
  tables drift year to year, so the mapper is tolerant — it maps whatever recognized tables a dump
  contains (`demolabs`, `workshops`, `training`, `contests`, `villages`, and the DC32/33 consolidated
  `pages`), records material/forum/video URLs found in columns **and** embedded in HTML descriptions,
  and reports any unrecognized table rather than dropping it silently. `vendors` is excluded.

Ingest reads SQL text only and records material **URLs** as metadata. There is no code path from
ingest to downloading a binary asset.

## Install

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run dcindex --help
```

## Usage

```bash
uv run dcindex init-db                       # create the database + FTS index
uv run dcindex ingest-url --edition dc33     # download (once, cached) + ingest DC33
uv run dcindex ingest-url --edition dc32     # …and more years
uv run dcindex ingest-dump ./dc30_mysqldump.txt --edition dc30   # offline, from a local file

uv run dcindex stats                         # row counts + per-category coverage
uv run dcindex events                        # list ingested DEF CON editions
uv run dcindex search "azure ad"             # full-text search; prints a #id per result
uv run dcindex search "hyper" --all          # every match (default shows 50; -n to set a limit)
uv run dcindex show 213                       # full detail: speakers, abstract, and known URLs
```

**Search** matches **substrings** (a trigram index), so `hyper` finds `hypervisor`; terms shorter
than 3 characters fall back to a `LIKE` scan so `ai`/`os`/`5g` still work. The match summary is
printed to **stderr**, so stdout carries only result rows and pipes cleanly.

**JSON output** for scripting — both `search` and `show` take `--json` and emit full session metadata
(abstract, track, room, time, source URL, speakers with affiliation/bio, and all material links) on
stdout, ready for `jq`:

```bash
uv run dcindex search "hypervisor" --json | jq '.[].title'    # array of full hit objects
uv run dcindex search "hypervisor" --json --all | jq length   # every match
uv run dcindex show 213 --json | jq '.materials'              # one full session object
```

Editions accept any of `dc30`, `defcon30`, `defcon-30`, `30`, or the year `2022`; when ingesting a
file the edition is also inferred from the filename (`dc30_mysqldump.txt`). Limit what you ingest
with `--categories` (e.g. `-c talk -c village`).

Data lives under `~/.local/share/dcindex/` (override with `--data-dir` or `DCINDEX_DATA_DIR`):
`dcindex.sqlite3`, `dumps/` (cached dump files — download once, reuse forever), and `dcindex.log`.

## Architecture

Layered backend; the dependency rule points inward. The CLI (and a future TUI/API) call **only** the
service layer — never repositories, parsers, or adapters directly.

```
cli ─► services ─► parsers          (mysqldump reader, Outel schedule mapper, materials classifier)
            │   └─► adapters         (DumpReader, HttpClient, DumpCache)
            └─► storage              (sqlite3 + FTS5, repositories, snapshots/provenance)
   everything ─► core / dto          (config, errors, editions, models; pydantic contracts)
```

- `ServiceContainer` is the DI root; `IngestService`, `SearchService`, `SessionService`,
  `StatsService` are the public API.
- Parsers are pure (SQL text → DTOs); all I/O (file reads, the one network fetch) lives in adapters.

## Coverage

| Years | Talks + speakers | Other activities | Materials |
|---|---|---|---|
| DC26–DC28 (2018–2020) | ✅ | — | links in talk descriptions |
| DC29 (2021) | ✅ | villages | ✅ links |
| DC30–DC31 (2022–2023) | ✅ | villages, demolabs, workshops, training, contests | ✅ links |
| DC32–DC33 (2024–2025) | ✅ | villages, `pages` (consolidated activities) | ✅ links |

`vendors` and CMS/utility tables (`articles`, `documents`, `map_matrix`, …) are intentionally skipped.

## Development

```bash
uv run pytest        # unit + integration tests, fully offline against a synthetic fixture dump
uv run ruff check .  # lint
```

The integration suite pins the Phase-1 invariant that ingesting writes only the database + provenance
rows — never a media/binary asset file.

## License

[MIT](LICENSE) © 2026 Evan H. Dygert.

dcindex indexes only **metadata** (titles, abstracts, speakers, and links). It does not redistribute
DEF CON or Outel content; all material links point back to their original sources. Respect the source
sites' terms of use.
