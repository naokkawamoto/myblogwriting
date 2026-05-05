from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer

from ot_marketing import __version__
from ot_marketing.env_load import bootstrap_env
from ot_marketing.llm import complete, default_model
from ot_marketing.output_store import write_markdown_output
from ot_marketing.paths import repo_root
from ot_marketing.workflows import build_note_user_message, build_share_user_message

bootstrap_env()

app = typer.Typer(no_args_is_help=True, help="Marketing prompts → LLM → outputs/")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _resolve_repo_path(rel: str) -> Path:
    p = (repo_root() / rel).resolve()
    if not p.is_file():
        raise typer.BadParameter(f"File not found: {p}")
    return p


@app.command()
def version() -> None:
    """Print CLI version."""
    typer.echo(__version__)


@app.command("call")
def call_cmd(
    prompt_file: Path = typer.Option(
        ...,
        "--prompt-file",
        exists=True,
        dir_okay=False,
        readable=True,
        help="Path to system/context markdown (absolute or cwd-relative).",
    ),
    user_file: Optional[Path] = typer.Option(
        None,
        "--user-file",
        exists=True,
        dir_okay=False,
        readable=True,
        help="Additional user message (appended after prompt file).",
    ),
    user_stdin: bool = typer.Option(
        False,
        "--stdin",
        help="Read additional user text from stdin (after prompt file).",
    ),
    provider: str = typer.Option(
        ...,
        "--provider",
        help="openai or anthropic",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        help="Override model id (defaults from OTM_OPENAI_MODEL / OTM_ANTHROPIC_MODEL).",
    ),
    system: str = typer.Option(
        "",
        "--system",
        help="Optional system message (OpenAI/Anthropic).",
    ),
    output_basename: str = typer.Option(
        "draft",
        "--output-basename",
        help="Output filename stem under outputs/YYYY-MM-DD/.",
    ),
) -> None:
    """Generic: one prompt file + optional user file/stdin → LLM → markdown file."""
    provider_l = provider.strip().lower()
    if provider_l not in ("openai", "anthropic"):
        raise typer.BadParameter("provider must be openai or anthropic")

    blob = _read_text(prompt_file)
    extras: list[str] = []
    if user_file:
        extras.append(_read_text(user_file))
    if user_stdin:
        stdin_text = sys.stdin.read()
        if stdin_text.strip():
            extras.append(stdin_text)
    user = blob if not extras else blob + "\n\n---\n\n" + "\n\n".join(extras)

    m = model or default_model(provider_l)  # type: ignore[arg-type]
    typer.echo(f"Calling {provider_l} model={m!r} …", err=True)
    text = complete(provider=provider_l, model=m, system=system, user=user)  # type: ignore[arg-type]
    out = write_markdown_output(
        basename=output_basename,
        body=text,
        extra_header=f"provider={provider_l} model={m}",
        source="cli",
    )
    typer.echo(str(out))


@app.command()
def note(
    task_file: Path = typer.Option(
        ...,
        "--task-file",
        exists=True,
        dir_okay=False,
        readable=True,
        help="Filled task text (e.g. copy of 99_task_input.md section).",
    ),
    provider: str = typer.Option(
        "openai",
        "--provider",
        help="openai or anthropic",
    ),
    model: Optional[str] = typer.Option(None, "--model"),
    output_basename: str = typer.Option("note-draft", "--output-basename"),
) -> None:
    """note: dist/note_writer_prompt.md + task file → LLM."""
    try:
        blob = build_note_user_message(_read_text(task_file))
    except FileNotFoundError as e:
        raise typer.BadParameter(str(e)) from e
    provider_l = provider.strip().lower()
    if provider_l not in ("openai", "anthropic"):
        raise typer.BadParameter("provider must be openai or anthropic")
    m = model or default_model(provider_l)  # type: ignore[arg-type]
    typer.echo(f"Calling {provider_l} model={m!r} …", err=True)
    text = complete(provider=provider_l, model=m, system="", user=blob)  # type: ignore[arg-type]
    out = write_markdown_output(
        basename=output_basename,
        body=text,
        extra_header=f"note provider={provider_l} model={m}",
        source="cli",
    )
    typer.echo(str(out))


@app.command()
def share(
    filled_file: Path = typer.Option(
        ...,
        "--filled-file",
        exists=True,
        dir_okay=False,
        readable=True,
        help="Your filled answers (title, URL, pasted text, etc.).",
    ),
    provider: str = typer.Option(
        "openai",
        "--provider",
        help="openai or anthropic",
    ),
    model: Optional[str] = typer.Option(None, "--model"),
    output_basename: str = typer.Option("share-draft", "--output-basename"),
) -> None:
    """share: prompts/ops/share_short_from_company.md + your filled block → LLM."""
    try:
        blob = build_share_user_message(_read_text(filled_file))
    except FileNotFoundError as e:
        raise typer.BadParameter(str(e)) from e
    provider_l = provider.strip().lower()
    if provider_l not in ("openai", "anthropic"):
        raise typer.BadParameter("provider must be openai or anthropic")
    m = model or default_model(provider_l)  # type: ignore[arg-type]
    typer.echo(f"Calling {provider_l} model={m!r} …", err=True)
    text = complete(provider=provider_l, model=m, system="", user=blob)  # type: ignore[arg-type]
    out = write_markdown_output(
        basename=output_basename,
        body=text,
        extra_header=f"share provider={provider_l} model={m}",
        source="cli",
    )
    typer.echo(str(out))


def main() -> None:
    app(prog_name="otm")


if __name__ == "__main__":
    main()
