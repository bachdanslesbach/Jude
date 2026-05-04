from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import typer
from rich import print as rprint
from rich.table import Table

from .adapters import DocxAdapter, TextAdapter
from .adapters.docx import PARAGRAPH_SEP
from .detect import DetectionPipeline
from .paths import default_db_path
from .redact import redact
from .rehydrate import rehydrate
from .store import Store
from .types import Mode

app = typer.Typer(no_args_is_help=True, add_completion=False)
matter_app = typer.Typer(no_args_is_help=True, help="Manage matters.")
app.add_typer(matter_app, name="matter")


@app.command()
def init() -> None:
    """Create the local database and verify spaCy models are installed."""

    db = default_db_path()
    Store(db).close()
    rprint(f"[green]Database ready at {db}[/green]")
    for model in ("en_core_web_md", "fr_core_news_md"):
        try:
            __import__("spacy").load(model)
            rprint(f"[green]spaCy model '{model}' OK[/green]")
        except OSError:
            rprint(
                f"[yellow]spaCy model '{model}' not installed. "
                f"Run: python -m spacy download {model}[/yellow]"
            )


@matter_app.command("create")
def matter_create(
    name: str,
    mode: Mode = Mode.STRICT,
    zero_retention: bool = typer.Option(
        False, "--zr", help="Attest the LLM endpoint is zero-retention (smart mode)."
    ),
) -> None:
    with Store(default_db_path()) as store:
        m = store.create_matter(
            name=name, mode=mode, zero_retention_attested=zero_retention
        )
    rprint(f"[green]Created matter[/green] {m.id} — {m.name} ({m.mode.value})")


@matter_app.command("list")
def matter_list() -> None:
    with Store(default_db_path()) as store:
        matters = store.list_matters()
    table = Table(title="Matters")
    for col in ("id", "name", "mode", "zr", "created_at"):
        table.add_column(col)
    for m in matters:
        table.add_row(
            m.id,
            m.name,
            m.mode.value,
            "yes" if m.zero_retention_attested else "no",
            m.created_at.isoformat() if m.created_at else "",
        )
    rprint(table)


@app.command(name="redact")
def redact_file(
    path: Path = typer.Argument(..., exists=True, readable=True),
    matter: str = typer.Option(..., help="Matter id."),
    out: Path | None = typer.Option(
        None, help="Output path. Defaults to <input>.redacted.<ext>"
    ),
) -> None:
    """Redact a .txt or .docx file."""

    with Store(default_db_path()) as store:
        m = store.get_matter(matter)
        if m is None:
            rprint(f"[red]Unknown matter: {matter}[/red]")
            raise typer.Exit(1)
        pipeline = DetectionPipeline(store=store, matter_id=matter)

        if path.suffix.lower() == ".docx":
            extraction = DocxAdapter.read(path)
            for w in extraction.warnings:
                rprint(f"[yellow]warning:[/yellow] {w}")
            result = redact(extraction.text, pipeline.detect(extraction.text), store, matter, m.mode)
            redacted_paragraphs = result.redacted_text.split(PARAGRAPH_SEP)
            target = out or path.with_suffix(".redacted.docx")
            DocxAdapter.write_redacted(path, target, redacted_paragraphs)
        else:
            text = TextAdapter.read(path)
            result = redact(text, pipeline.detect(text), store, matter, m.mode)
            target = out or path.with_suffix(".redacted" + path.suffix)
            TextAdapter.write(target, result.redacted_text)

    rprint(f"[green]Redacted {len(result.entities_used)} entities[/green] → {target}")


@app.command()
def entities(matter: str = typer.Option(..., help="Matter id.")) -> None:
    """Show every entity stored for a matter (this contains real names)."""

    with Store(default_db_path()) as store:
        ents = store.list_entities(matter)
    table = Table(title=f"Entities for matter {matter}")
    for col in ("pseudonym", "type", "canonical", "context", "user"):
        table.add_column(col)
    for e in ents:
        table.add_row(
            e.pseudonym,
            e.entity_type.value,
            e.canonical,
            e.public_context or "",
            "yes" if e.user_marked else "no",
        )
    rprint(table)


@app.command(name="rehydrate")
def rehydrate_file(
    path: Path = typer.Argument(..., exists=True, readable=True),
    matter: str = typer.Option(..., help="Matter id."),
    out: Path | None = typer.Option(None),
) -> None:
    """Replace pseudonyms in an LLM output back to real names."""

    with Store(default_db_path()) as store:
        text = TextAdapter.read(path)
        result = rehydrate(text, store, matter)
    target = out or path.with_suffix(".rehydrated" + path.suffix)
    TextAdapter.write(target, result)
    rprint(f"[green]Rehydrated[/green] → {target}")


@app.command()
def ui() -> None:
    """Launch the Streamlit UI."""

    here = Path(__file__).parent / "ui" / "app.py"
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(here)], check=False)


if __name__ == "__main__":
    app()
