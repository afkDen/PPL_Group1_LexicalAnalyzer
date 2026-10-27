"""Standard-library-only lexical entry point; imports no compiler analysis."""

import argparse
import os
import sys
import tempfile
from pathlib import Path
from typing import TextIO

from ternfold.frontend.classroom_report import classroom_report
from ternfold.frontend.diagnostics import DiagnosticReport, diagnostic_from_source_error
from ternfold.frontend.lexer import lex
from ternfold.frontend.render import RenderContext, render_text
from ternfold.frontend.source import SourceManager


def _write(stream: TextIO, text: str) -> None:
    try:
        stream.write(text)
        stream.flush()
    except (OSError, ValueError, UnicodeError) as error:
        # Python retries buffered output at shutdown. Redirect the failed fd so
        # that retry cannot replace the documented exit status with exit 120.
        try:
            descriptor = os.open(os.devnull, os.O_WRONLY)
            try:
                os.dup2(descriptor, stream.fileno())
            finally:
                os.close(descriptor)
        except (OSError, ValueError):
            pass
        raise OSError("unable to write analyzer output") from error


def _publish(path: Path, data: bytes, source: Path) -> None:
    if path.resolve() == source.resolve() or (path.exists() and os.path.samefile(path, source)):
        raise ValueError("the report cannot replace its source")
    if not path.parent.is_dir():
        raise ValueError("output directory must already exist")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".lexical-", delete=False) as file:
            temporary = Path(file.name)
            file.write(data)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ternfold lexical analyzer (offline, DFA-driven).")
    parser.add_argument("file", help="UTF-8 source with the exact .tfd extension")
    parser.add_argument("--output-dir", default=".", help="existing directory for Symbol Table.txt")
    args = parser.parse_args(argv)
    source = Path(args.file)
    report = Path(args.output_dir) / "Symbol Table.txt"
    try:
        if source.suffix != ".tfd":
            raise ValueError("source input must have the exact .tfd extension")
        loaded = SourceManager().load_path(source)
        if loaded.source is None:
            assert loaded.errors
            # Encoding failures cannot be represented as valid source lexemes.
            # Keep the report honest and put the raw-byte diagnostic on stderr.
            _publish(report, b"TOKEN TYPE\tLEXEME\n", source)
            diagnostics = DiagnosticReport(
                tuple(diagnostic_from_source_error(e) for e in loaded.errors)
            )
            status = 1
        else:
            result = lex(loaded.source)
            _publish(report, classroom_report(result).encode("utf-8"), source)
            diagnostics = result.diagnostics
            status = int(diagnostics.has_errors)
        message = render_text(diagnostics, RenderContext(root=source.resolve().parent))
        if message:
            _write(sys.stderr, message)
        _write(sys.stdout, "Wrote " + str(report) + "\n")
        return status
    except (OSError, ValueError) as error:
        try:
            _write(sys.stderr, "Lexical analyzer: " + str(error) + "\n")
        except OSError:
            pass
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
