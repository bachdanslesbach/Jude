from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import typer
from rich import print as rprint
from rich.table import Table

from .adapters import DocxAdapter, PdfAdapter, TextAdapter, XlsxAdapter
from .adapters.docx import PARAGRAPH_SEP
from .context import fill_missing_context
from .detect import DetectionPipeline
from .paths import default_db_path
from .redact import redact, redact_two_pass
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
    import spacy.util

    en_options = ("en_core_web_lg", "en_core_web_md")
    if any(spacy.util.is_package(m) for m in en_options):
        installed = next(m for m in en_options if spacy.util.is_package(m))
        rprint(f"[green]English NER model '{installed}' OK[/green]")
    else:
        rprint(
            "[yellow]English NER model missing. Run:\n"
            "  python -m spacy download en_core_web_lg   (recommended)\n"
            "  python -m spacy download en_core_web_md   (lighter fallback)[/yellow]"
        )
    if spacy.util.is_package("fr_core_news_md"):
        rprint("[green]French NER model 'fr_core_news_md' OK[/green]")
    else:
        rprint(
            "[yellow]French NER model missing. Run:\n"
            "  python -m spacy download fr_core_news_md[/yellow]"
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
    paths: list[Path] = typer.Argument(
        ...,
        help="One or more .txt / .docx / .pdf / .xlsx files to redact.",
        exists=True,
        readable=True,
    ),
    matter: str = typer.Option(..., help="Matter id."),
    out: Path | None = typer.Option(
        None,
        help="Output path. Only valid with a single input. "
        "Defaults to <input>.redacted.<ext>.",
    ),
    ocr: bool = typer.Option(
        False,
        "--ocr",
        help="For PDFs only: if the file is image-only, run ocrmypdf locally "
        "to produce searchable text first. Requires tesseract installed.",
    ),
) -> None:
    """Redact one or more .txt / .docx / .pdf / .xlsx files. When multiple
    files are passed, they share the same per-matter dictionary so an
    entity detected in file 1 keeps the same pseudonym in file 2."""

    if out is not None and len(paths) > 1:
        rprint(
            "[red]--out is only valid with a single input file. "
            "Drop --out to use the default <input>.redacted.<ext> per file.[/red]"
        )
        raise typer.Exit(2)

    with Store(default_db_path()) as store:
        m = store.get_matter(matter)
        if m is None:
            rprint(f"[red]Unknown matter: {matter}[/red]")
            raise typer.Exit(1)
        pipeline = DetectionPipeline(store=store, matter_id=matter)

        for idx, path in enumerate(paths, 1):
            if len(paths) > 1:
                rprint(f"[bold]({idx}/{len(paths)}) {path.name}[/bold]")
            _redact_one(path, store, m, matter, pipeline, out, ocr)


def _redact_one(
    path: Path,
    store: Store,
    m,  # type: ignore[no-untyped-def]
    matter: str,
    pipeline: DetectionPipeline,
    out: Path | None,
    ocr: bool,
) -> None:
    """Redact a single file. Extracted so the multi-file `jude redact`
    loop can reuse the per-suffix dispatch logic."""

    suffix = path.suffix.lower()
    if suffix == ".docx":
        extraction = DocxAdapter.read(path)
        for w in extraction.warnings:
            rprint(f"[yellow]warning:[/yellow] {w}")
        result = redact(extraction.text, pipeline.detect(extraction.text), store, matter, m.mode)
        redacted_paragraphs = result.redacted_text.split(PARAGRAPH_SEP)
        target = out or path.with_suffix(".redacted.docx")
        DocxAdapter.write_redacted(path, target, redacted_paragraphs)
    elif suffix == ".xlsx":
        extraction_xlsx = XlsxAdapter.read(path)
        for w in extraction_xlsx.warnings:
            rprint(f"[yellow]warning:[/yellow] {w}")
        result = redact(
            extraction_xlsx.text,
            pipeline.detect(extraction_xlsx.text),
            store, matter, m.mode,
        )
        replacements = {
            ent.canonical: ent.pseudonym for ent in result.entities_used
        }
        for surface in {d.text for d in result.detections}:
            ent = store.find_entity_by_surface(matter, surface)
            if ent:
                replacements[surface] = ent.pseudonym
        target = out or path.with_suffix(".redacted.xlsx")
        XlsxAdapter.write_redacted(path, target, replacements)
    elif suffix == ".pdf":
        try:
            extraction = PdfAdapter.read(path, enable_ocr=ocr)
        except Exception as e:
            rprint(f"[red]PDF read failed:[/red] {e}")
            raise typer.Exit(1) from e
        for w in extraction.warnings:
            rprint(f"[yellow]warning:[/yellow] {w}")
        if not extraction.text.strip():
            rprint(
                "[red]No extractable text.[/red] "
                "If this is a scanned PDF, re-run with --ocr."
            )
            raise typer.Exit(1)
        result = redact(extraction.text, pipeline.detect(extraction.text), store, matter, m.mode)
        target = out or path.with_suffix(".redacted.pdf")
        if target.suffix.lower() == ".pdf" and extraction.is_text_pdf:
            replacements = {
                form: ent.pseudonym
                for ent in result.entities_used
                for form in ent.surface_forms
            }
            for ent in result.entities_used:
                replacements.setdefault(ent.canonical, ent.pseudonym)
            PdfAdapter.write_redacted(path, target, replacements)
        else:
            TextAdapter.write(target, result.redacted_text)
            rprint(
                "[yellow]note:[/yellow] redacted output written as plain text "
                "(use --out file.pdf for native PDF write-back on text PDFs)."
            )
    else:
        text = TextAdapter.read(path)
        result = redact(text, pipeline.detect(text), store, matter, m.mode)
        target = out or path.with_suffix(".redacted" + path.suffix)
        TextAdapter.write(target, result.redacted_text)

    rprint(f"[green]Redacted {len(result.entities_used)} entities[/green] → {target}")


def _read_text(path: Path, ocr: bool = False) -> str:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return DocxAdapter.read(path).text
    if suffix == ".xlsx":
        return XlsxAdapter.read(path).text
    if suffix == ".pdf":
        return PdfAdapter.read(path, enable_ocr=ocr).text
    return TextAdapter.read(path)


@app.command()
def review(
    path: Path = typer.Argument(
        ..., exists=True, readable=True, help="A .txt / .docx / .pdf / .xlsx file."
    ),
    matter: str = typer.Option(..., help="Matter id."),
    ocr: bool = typer.Option(False, "--ocr", help="OCR an image-only PDF first."),
) -> None:
    """List what Jude did NOT redact and does not know as public.

    Every capitalised phrase and identifier-like token left in the
    redacted text, in context, for one confirmation pass — the
    fail-closed half of "no misses". Detected entities are recorded in
    the matter's dictionary (as with `redact`); no file is written.
    """

    from rich.markup import escape

    from .review import unverified_terms

    with Store(default_db_path()) as store:
        m = store.get_matter(matter)
        if m is None:
            rprint(f"[red]Unknown matter: {matter}[/red]")
            raise typer.Exit(1)
        text = _read_text(path, ocr=ocr)
        pipeline = DetectionPipeline(store=store, matter_id=matter)
        result = redact_two_pass(text, pipeline, store, matter, m.mode)
        terms = unverified_terms(text, result.detections)

    rprint(
        f"[green]{len(result.detections)} spans redacted[/green] · "
        f"[yellow]{len(terms)} unverified term{'s' if len(terms) != 1 else ''}[/yellow]"
    )
    if not terms:
        rprint("[green]✓ Nothing left that looks like an identifier.[/green]")
        return
    rprint(
        "[dim]Capitalised or identifier-like, neither redacted nor known as public. "
        "Add what identifies a party with `jude entities` / the UI, then re-run.[/dim]"
    )
    for t in terms:
        rprint(f"  [bold]{escape(t.text)}[/bold] ×{t.count}   [dim]{escape(t.context)}[/dim]")


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
def enrich(matter: str = typer.Option(..., help="Matter id.")) -> None:
    """Auto-fill `public context` from the bundled known-entities dataset."""

    with Store(default_db_path()) as store:
        n = fill_missing_context(store, matter)
    rprint(f"[green]Filled public context for {n} entities.[/green]")


@app.command(name="export")
def export_matter(
    matter: str = typer.Argument(..., help="Matter id."),
    out: Path | None = typer.Option(
        None, help="Output path. Defaults to ./jude-matter-<id>.json"
    ),
) -> None:
    """Dump a matter's entities, conversations, and messages as JSON."""

    import json as _json

    with Store(default_db_path()) as store:
        try:
            data = store.export_matter_json(matter)
        except ValueError as e:
            rprint(f"[red]{e}[/red]")
            raise typer.Exit(1) from e
    target = out or Path(f"./jude-matter-{matter}.json")
    target.write_text(_json.dumps(data, ensure_ascii=False, indent=2))
    rprint(f"[green]Exported matter[/green] → {target}")


@app.command()
def ui() -> None:
    """Launch the Streamlit UI.

    Suppresses Streamlit's first-run email prompt and disables anonymous
    usage telemetry — the tool's whole point is local-only operation, so
    sending nothing back to Streamlit is the right default.
    """

    _silence_streamlit_prompts()
    here = Path(__file__).parent / "ui" / "app.py"
    env = {
        **os.environ,
        "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
        "STREAMLIT_SERVER_HEADLESS": "false",
    }
    subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(here),
            "--browser.gatherUsageStats=false",
        ],
        check=False,
        env=env,
    )


def _silence_streamlit_prompts() -> None:
    """Pre-create ~/.streamlit/credentials.toml so Streamlit's first-run email
    prompt never appears. Idempotent — only writes if the file is missing."""

    creds = Path.home() / ".streamlit" / "credentials.toml"
    if creds.exists():
        return
    creds.parent.mkdir(parents=True, exist_ok=True)
    creds.write_text('[general]\nemail = ""\n', encoding="utf-8")


if __name__ == "__main__":
    app()
