"""Honest frontend-foundation entry point; no language execution yet."""

import argparse
import json
import os
import sys
import tempfile
from io import TextIOWrapper
from pathlib import Path
from typing import TextIO

from ternfold import __version__
from ternfold.analysis.machines import PlannedProgram, plan_dump
from ternfold.core.dump import core_dump
from ternfold.core.nodes import VerifiedCore
from ternfold.core.verify import VerificationError
from ternfold.driver import check, compile_source
from ternfold.frontend.ast_dump import ast_dump
from ternfold.frontend.diagnostics import (
    DiagnosticReport,
    ValidResult,
    diagnostic_from_source_error,
)
from ternfold.frontend.lexer import lex
from ternfold.frontend.lexical_report import render_symbol_table, token_dump
from ternfold.frontend.parser import ParserResourceError, parse
from ternfold.frontend.render import ColorMode, RenderContext, render_json, render_text
from ternfold.frontend.source import SourceManager


def _quiet_failed_stream(stream: TextIO) -> None:
    """Prevent a buffered pipe failure from being retried during Python shutdown."""
    try:
        descriptor = stream.fileno()
        sink = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(sink, descriptor)
        finally:
            os.close(sink)
    except (OSError, ValueError):
        # Non-file streams (e.g. embedding hosts) may not expose a descriptor.
        try:
            stream.close()
        except (OSError, UnicodeError):
            pass


def _write(stream: TextIO, text: str) -> None:
    try:
        if isinstance(stream, TextIOWrapper):
            stream.reconfigure(encoding="utf-8", errors="strict", newline="\n")
        stream.write(text)
        stream.flush()
    except (OSError, UnicodeError):
        _quiet_failed_stream(stream)
        raise
    except ValueError as error:
        # Closed embedding streams raise ValueError rather than an OS pipe error.
        _quiet_failed_stream(stream)
        raise OSError("output stream is closed or unavailable") from error


def _host_error(message: str, diagnostic_format: str) -> int:
    text = (
        json.dumps({"schema_version": 1, "host_error": message}, ensure_ascii=True, sort_keys=True)
        if diagnostic_format == "json"
        else "ternfold: " + json.dumps(message, ensure_ascii=True)
    )
    try:
        _write(sys.stderr, text + "\n")
    except (OSError, UnicodeError):
        pass
    return 2


def _publish_report(destination: Path, text: str) -> None:
    """Replace only the explicitly requested output, after a complete UTF-8 write."""
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=destination.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        temporary.replace(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _inspection_command(args: argparse.Namespace) -> int:
    try:
        path = Path(args.file)
        if path.suffix != ".tfd":
            return _host_error("source input must have the .tfd extension", args.diagnostic_format)
        path = path.resolve()
        root = Path(args.root).resolve() if args.root is not None else path.parent
        if not root.is_dir() or not path.is_relative_to(root):
            return _host_error(
                "source input must be inside the source root", args.diagnostic_format
            )
        table_path: str | None = getattr(args, "symbol_table", None)
        destination = Path(table_path).resolve() if table_path is not None else None
        if destination is not None and (
            destination == path or (destination.exists() and destination.samefile(path))
        ):
            return _host_error(
                "symbol table output must not overwrite the source", args.diagnostic_format
            )
        loaded = SourceManager().load_path(path)
    except (OSError, ValueError) as error:
        return _host_error(str(error), args.diagnostic_format)
    try:
        is_tty = sys.stderr.isatty()
    except (OSError, ValueError) as error:
        return _host_error(str(error), args.diagnostic_format)
    context = RenderContext(
        root=root,
        color=ColorMode(args.color),
        is_tty=is_tty,
        no_color="NO_COLOR" in os.environ,
        term_dumb=os.environ.get("TERM") == "dumb",
    )
    result = lex(loaded.source) if loaded.source is not None else None
    diagnostics = (
        result.diagnostics
        if result is not None
        else DiagnosticReport(tuple(diagnostic_from_source_error(error) for error in loaded.errors))
    )
    try:
        if result is not None:
            if args.command == "ast":
                if not diagnostics.has_errors:
                    parsed = parse(result.tokens, root_module=True)
                    diagnostics = parsed.diagnostics
                    _write(sys.stdout, ast_dump(parsed, context))
            else:
                if destination is not None:
                    _publish_report(destination, render_symbol_table(result, context))
                _write(sys.stdout, token_dump(result, context))
        if diagnostics.has_errors:
            _write(
                sys.stderr,
                render_json(diagnostics, context)
                if args.diagnostic_format == "json"
                else render_text(diagnostics, context),
            )
    except (OSError, UnicodeError) as error:
        return _host_error(str(error), args.diagnostic_format)
    except (ParserResourceError, MemoryError) as error:
        return _host_error(
            str(error) or "host frontend memory capacity exhausted", args.diagnostic_format
        )
    return 1 if diagnostics.has_errors else 0


def _check_command(args: argparse.Namespace) -> int:
    try:
        path = Path(args.file)
        root = Path(args.root).resolve() if args.root is not None else path.resolve().parent
        result = (
            compile_source(path, root=root) if args.command == "core" else check(path, root=root)
        )
        context = RenderContext(
            root=root,
            color=ColorMode(args.color),
            is_tty=sys.stderr.isatty(),
            no_color="NO_COLOR" in os.environ,
            term_dumb=os.environ.get("TERM") == "dumb",
        )
        if args.command == "plan" and isinstance(result, ValidResult):
            assert isinstance(result.value, PlannedProgram)
            _write(sys.stdout, plan_dump(result.value, context))
        if args.command == "core" and isinstance(result, ValidResult):
            assert isinstance(result.value, VerifiedCore)
            _write(sys.stdout, core_dump(result.value, context))
        if result.diagnostics.has_errors:
            _write(
                sys.stderr,
                render_json(result.diagnostics, context)
                if args.diagnostic_format == "json"
                else render_text(result.diagnostics, context),
            )
        return 1 if result.diagnostics.has_errors else 0
    except VerificationError as error:
        try:
            _write(
                sys.stderr,
                json.dumps(
                    {
                        "schema_version": 1,
                        "internal_error": str(error),
                        "phase": "Core verification",
                    },
                    ensure_ascii=True,
                )
                + "\n",
            )
        except OSError:
            return 2
        return 70
    except (OSError, ValueError, UnicodeError) as error:
        return _host_error(str(error), args.diagnostic_format)
    except (ParserResourceError, RecursionError, MemoryError) as error:
        return _host_error(
            str(error) or "host frontend/type-checking memory capacity exhausted",
            args.diagnostic_format,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ternfold", description="Ternfold frontend foundation (compiler not implemented)"
    )
    parser.add_argument("--version", action="version", version=f"ternfold {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="report implemented capabilities")
    tokens = commands.add_parser(
        "tokens", help="inspect lexical tokens without parsing or execution"
    )
    tokens.add_argument("file")
    tokens.add_argument("--root")
    tokens.add_argument("--symbol-table")
    tokens.add_argument("--diagnostic-format", choices=["text", "json"], default="text")
    tokens.add_argument("--color", choices=["auto", "always", "never"], default="auto")
    ast_command = commands.add_parser(
        "ast", help="inspect surface syntax without resolution or execution"
    )
    ast_command.add_argument("file")
    ast_command.add_argument("--root")
    ast_command.add_argument("--diagnostic-format", choices=["text", "json"], default="text")
    ast_command.add_argument("--color", choices=["auto", "always", "never"], default="auto")
    check_command = commands.add_parser(
        "check",
        help="validate the full frontend without execution",
        description="Checks names, types and machine dependency plans. Does not execute programs.",
    )
    check_command.add_argument("file")
    check_command.add_argument("--root")
    check_command.add_argument("--diagnostic-format", choices=["text", "json"], default="text")
    check_command.add_argument("--color", choices=["auto", "always", "never"], default="auto")
    plan_command = commands.add_parser(
        "plan",
        help="inspect static machine dependencies and scheduling as JSON",
        description="Static machine plans. Guards remain runtime checks; no program execution.",
    )
    plan_command.add_argument("file")
    plan_command.add_argument("--root")
    plan_command.add_argument("--diagnostic-format", choices=["text", "json"], default="text")
    plan_command.add_argument("--color", choices=["auto", "always", "never"], default="auto")
    core_command = commands.add_parser("core", help="inspect verified Core JSON without execution")
    core_command.add_argument("file")
    core_command.add_argument("--root")
    core_command.add_argument("--diagnostic-format", choices=["text", "json"], default="text")
    core_command.add_argument("--color", choices=["auto", "always", "never"], default="auto")
    args = parser.parse_args(argv)
    if args.command in {"check", "plan", "core"}:
        return _check_command(args)
    if args.command in {"tokens", "ast"}:
        return _inspection_command(args)
    if args.command == "status":
        print(
            json.dumps(
                {
                    "version": __version__,
                    "phase": "frontend-foundation",
                    "implemented": [
                        "status",
                        "--version",
                        "--help",
                        "tokens",
                        "ast",
                        "check",
                        "plan",
                        "core",
                    ],
                    "check_scope": "full-frontend",
                    "type_checking": True,
                    "frontend_components": [
                        "source-snapshots",
                        "structured-diagnostics",
                        "lexer",
                        "parser",
                        "resolution",
                        "types",
                        "machine-planning",
                        "Float",
                    ],
                    "next_task": "M09",
                    "language_execution": False,
                },
                sort_keys=True,
            )
        )
        return 0
    return 2
