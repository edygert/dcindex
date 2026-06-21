"""dcindex CLI.

Commands are thin wrappers that build a ServiceContainer and call services — no business logic here,
so a future TUI/FastAPI front-end shares the exact same operations.
"""

from __future__ import annotations

import webbrowser
from pathlib import Path

import typer

from dcindex import __version__
from dcindex.core.config import load_settings
from dcindex.core.errors import DcIndexError
from dcindex.services import ServiceContainer

app = typer.Typer(
    add_completion=False,
    help="Local-first DEF CON schedule indexer (Outel MySQL dumps, DC26+). Metadata only.",
)

DataDir = Path | None
_data_dir_opt = typer.Option(None, "--data-dir", help="Override the data directory (DB + caches).")
_edition_opt = typer.Option(None, "--edition", "-e", help="DEF CON edition, e.g. dc30 (else inferred).")
_categories_opt = typer.Option(
    None, "--categories", "-c",
    help="Limit categories (repeatable): talk demolab workshop training contest village page.",
)


def _container(data_dir: DataDir, *, ensure_schema: bool = True) -> ServiceContainer:
    settings = load_settings(**({"data_dir": data_dir} if data_dir else {}))
    return ServiceContainer(settings, ensure_schema=ensure_schema)


def _print_report(console, report) -> None:
    colour = "green" if report.status == "ok" and not report.anomalies else (
        "red" if report.status == "error" else "yellow"
    )
    cache = " (cached)" if report.from_cache else ""
    console.print(
        f"[bold {colour}]{report.edition}[/]{cache}  "
        f"sessions={report.sessions_upserted} speakers={report.speakers_upserted} "
        f"materials={report.materials_upserted}  · {report.status}"
    )
    if report.by_category:
        cats = "  ".join(f"{k}={v}" for k, v in sorted(report.by_category.items()))
        console.print(f"  {cats}", style="dim")
    console.print(
        f"  no-abstract={report.sessions_without_abstract} "
        f"no-speakers={report.sessions_without_speakers} "
        f"no-materials={report.sessions_without_materials}",
        style="dim",
    )
    for note in report.anomalies:
        console.print(f"  ! {note}", style="yellow")
    for err in report.errors:
        console.print(f"  ! {err}", style="red")


@app.command("init-db")
def init_db(data_dir: DataDir = _data_dir_opt) -> None:
    """Create the SQLite database, schema, and FTS index (idempotent)."""
    with _container(data_dir, ensure_schema=False) as app_:
        version = app_.init_db()
        typer.echo(f"schema ready (v{version}) at {app_.settings.db_path}")


@app.command("ingest-dump")
def ingest_dump(
    paths: list[Path] = typer.Argument(..., help="One or more local MySQL dump files (.txt/.sql/.gz)."),
    edition: str | None = _edition_opt,
    categories: list[str] | None = _categories_opt,
    data_dir: DataDir = _data_dir_opt,
) -> None:
    """Ingest one or more local Outel MySQL dump files (offline, metadata only)."""
    from rich.console import Console

    console = Console()
    with _container(data_dir) as app_:
        with console.status("starting…", spinner="dots") as status:
            for path in paths:
                try:
                    report = app_.ingest.ingest_dump(
                        str(path), edition=edition, categories=categories,
                        progress=lambda m: status.update(m),
                    )
                except DcIndexError as exc:
                    console.print(f"[red]{path}: {exc}[/]")
                    continue
                _print_report(console, report)


@app.command("ingest-url")
def ingest_url(
    url: str | None = typer.Argument(None, help="Dump URL (else built from --edition)."),
    edition: str | None = _edition_opt,
    refresh: bool = typer.Option(False, "--refresh", help="Force re-download even if cached."),
    categories: list[str] | None = _categories_opt,
    data_dir: DataDir = _data_dir_opt,
) -> None:
    """Fetch a published Outel dump (once; cached) and ingest it. Re-runs use the cache, no network."""
    from rich.console import Console

    console = Console()
    if not url and not edition:
        console.print("[red]provide a URL or --edition (e.g. --edition dc33)[/]")
        raise typer.Exit(2)
    with _container(data_dir) as app_:
        try:
            with console.status("starting…", spinner="dots") as status:
                report = app_.ingest.ingest_url(
                    url, edition=edition, refresh=refresh, categories=categories,
                    progress=lambda m: status.update(m),
                )
        except DcIndexError as exc:
            console.print(f"[red]{exc}[/]")
            raise typer.Exit(1) from exc
        _print_report(console, report)


@app.command()
def stats(data_dir: DataDir = _data_dir_opt) -> None:
    """Show row counts and per-category coverage."""
    with _container(data_dir) as app_:
        overview = app_.stats.overview()
        typer.echo("  ".join(f"{k}={v}" for k, v in overview.items()))
        for row in app_.stats.by_category():
            typer.echo(f"  {row['category']}: {row['sessions']} sessions")


@app.command()
def events(data_dir: DataDir = _data_dir_opt) -> None:
    """List ingested DEF CON editions."""
    with _container(data_dir) as app_:
        rows = app_.stats.events()
        if not rows:
            typer.echo("(no editions ingested yet — try 'dcindex ingest-url --edition dc33')")
            return
        for row in rows:
            year = row["year"] or "?"
            typer.echo(f"{row['slug']:12} {row['name']:14} {year}  {row['sessions']:5} sessions")


@app.command()
def search(
    query: str = typer.Argument(..., help="Full-text query over title/abstract/speakers/track."),
    limit: int = typer.Option(50, "--limit", "-n", help="Max results to show."),
    show_all: bool = typer.Option(False, "--all", help="Show every match (ignores --limit)."),
    data_dir: DataDir = _data_dir_opt,
) -> None:
    """Full-text search across ingested sessions."""
    with _container(data_dir) as app_:
        total = app_.search.count(query)
        rows = app_.search.search(query, None if show_all else limit)
        if not rows:
            typer.echo("(no matches)")
            return
        for row in rows:
            speakers = f" — {row['speakers_text']}" if row["speakers_text"] else ""
            typer.echo(f"#{row['id']:<6} [{row['event_name']}/{row['category']}] {row['title']}{speakers}")
        # Summary goes to stderr so it never pollutes piped/redirected result rows on stdout.
        if len(rows) < total:
            typer.echo(f"showing {len(rows)} of {total} matches (use --all or -n to see more).", err=True)
        else:
            typer.echo(
                f"{total} match{'es' if total != 1 else ''}. Use 'dcindex show <id>' for detail.",
                err=True,
            )


@app.command()
def show(
    session_id: int = typer.Argument(..., help="Session id (the #number from `search`)."),
    data_dir: DataDir = _data_dir_opt,
) -> None:
    """Show full detail for one session: speakers, abstract, and all known material links."""
    with _container(data_dir) as app_:
        s = app_.sessions.get(session_id)
        if s is None:
            typer.secho(f"no session with id {session_id}", fg=typer.colors.RED)
            raise typer.Exit(1)

        typer.secho(s.title, bold=True)
        meta = " · ".join(x for x in (s.event_name, s.category.value, s.room, s.starts_at) if x)
        if meta:
            typer.echo(meta)
        if s.track:
            typer.echo(f"Track:    {s.track}")
        if s.speakers:
            names = ", ".join(
                sp.name + (f" ({sp.affiliation})" if sp.affiliation else "") for sp in s.speakers
            )
            typer.echo(f"Speakers: {names}")
        if s.source_url:
            typer.echo(f"Source:   {s.source_url}")
        if s.abstract:
            typer.echo(f"\n{s.abstract}")
        if s.materials:
            typer.echo("\nMaterials & links (open manually — nothing is downloaded):")
            for m in s.materials:
                typer.echo(f"  [{m.kind.value:10}] {m.url}")
        else:
            typer.echo("\nMaterials & links: none recorded")


@app.command()
def materials(
    session_id: int = typer.Argument(..., help="Session id (the #number from `search`)."),
    open_links: bool = typer.Option(
        False, "--open", help="Open each link in your default browser (manual access)."
    ),
    data_dir: DataDir = _data_dir_opt,
) -> None:
    """List a session's known supplemental URLs for manual access (never downloads anything)."""
    with _container(data_dir) as app_:
        mats = app_.sessions.materials(session_id)
        if mats is None:
            typer.secho(f"no session with id {session_id}", fg=typer.colors.RED)
            raise typer.Exit(1)
        if not mats:
            typer.echo("(no links recorded for this session)")
            return
        for m in mats:
            label = f" — {m.title}" if m.title and m.title != "Link" else ""
            typer.echo(f"[{m.kind.value:10}] {m.url}{label}")
            if open_links:
                webbrowser.open(m.url)
        if open_links:
            typer.echo(f"\nopened {len(mats)} link(s) in your browser")


@app.command()
def version() -> None:
    """Print the dcindex version."""
    typer.echo(__version__)


if __name__ == "__main__":
    app()
