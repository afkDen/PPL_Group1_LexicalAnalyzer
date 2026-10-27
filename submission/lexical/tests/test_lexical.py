"""Standard-library acceptance tests for the actual distributed analyzer."""

import ast
import json
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ternfold.frontend.classroom_report import classroom_report  # noqa: E402
from ternfold.frontend.diagnostics import ErrorResult  # noqa: E402
from ternfold.frontend.lexer import lex  # noqa: E402
from ternfold.frontend.source import SourceFile, SourceId  # noqa: E402
from ternfold.frontend.tokens import TokenKind, name_terminal, name_transition  # noqa: E402

KEYWORDS = (
    "as div else emit enum false fn for from guard if import in input let machine "
    "match next output pub record rejects state stdin stdout to true yields"
).split()
RESERVED = (
    "Int Float Bool Text Char Unit List Option Decision step len at append map fold range "
    "int_text bool_text parse_int text_len text_at text_slice int_float float_int float_text"
).split()
ARITHMETIC = ["+", "-", "/", "*", "%", "div", "^"]
BOOLEAN = ["&&", "||", "!", ">", "<", "==", "!=", ">=", "<="]


def scan(text, cap=100):
    return lex(SourceFile(SourceId(0), "test.tfd", text.encode("utf-8")), max_diagnostics=cap)


def command(path, directory, **env):
    return subprocess.run(
        [
            sys.executable,
            "-S",
            str(ROOT / "analyzer.py"),
            str(path),
            "--output-dir",
            str(directory),
        ],
        cwd=ROOT,
        env={**os.environ, **env},
        capture_output=True,
        check=False,
        timeout=15,
    )


class LexicalTests(unittest.TestCase):
    def test_all_keyword_and_reserved_dfa_terminals_and_identifier_boundaries(self):
        for word in KEYWORDS + RESERVED:
            with self.subTest(word=word):
                state = 0
                for char in word:
                    state = name_transition(state, char)
                kind, reserved = name_terminal(state)
                self.assertEqual(kind.value, word.upper() if word in KEYWORDS else "IDENT")
                self.assertEqual(reserved, word in RESERVED)
                result = scan(word + " " + word + "x " + word + "_2")
                self.assertFalse(result.diagnostics.has_errors)
                self.assertEqual([t.kind for t in result.tokens[1:-1]], [TokenKind.IDENT] * 2)
                self.assertFalse(any(t.reserved_name for t in result.tokens[1:-1]))
        self.assertEqual(
            [t.kind.value for t in scan("_ __ _a A2 _2 let letter").tokens[:-1]],
            ["UNDERSCORE", "IDENT", "IDENT", "IDENT", "IDENT", "LET", "IDENT"],
        )
        self.assertEqual(len(KEYWORDS), 28)
        self.assertEqual(len(RESERVED), 25)

    def test_recognition_never_uses_input_word_lookup_or_regex(self):
        import ternfold.frontend.tokens as tokens

        class ForbiddenLookup(dict):
            def get(self, *args):
                raise AssertionError("input word lookup attempted")

            def __contains__(self, item):
                raise AssertionError("input word set matching attempted")

        with (
            patch.object(tokens, "KEYWORDS", ForbiddenLookup()),
            patch.object(tokens, "RESERVED_NAMES", ForbiddenLookup()),
        ):
            result = scan("let letter Int Intensity from to div dividend")
            self.assertEqual(
                [t.kind.value for t in result.tokens[:-1]],
                ["LET", "IDENT", "IDENT", "IDENT", "FROM", "TO", "DIV", "IDENT"],
            )
            self.assertTrue(result.tokens[2].reserved_name)
        lexer_source = (ROOT / "ternfold/frontend/lexer.py").read_text(encoding="utf-8")
        tree = ast.parse(lexer_source)
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
        self.assertTrue(
            any(isinstance(n.func, ast.Name) and n.func.id == "name_transition" for n in calls)
        )
        self.assertTrue(
            any(isinstance(n.func, ast.Name) and n.func.id == "number_transition" for n in calls)
        )
        for module in (ROOT / "ternfold").rglob("*.py"):
            syntax = ast.parse(module.read_text(encoding="utf-8"))
            for node in ast.walk(syntax):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    names = (
                        [a.name.split(".")[0] for a in node.names]
                        if isinstance(node, ast.Import)
                        else [(node.module or "").split(".")[0]]
                    )
                    self.assertFalse(
                        set(names) & {"re", "regex", "ply", "sly", "lark", "antlr4"}, module
                    )
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, {"eval", "exec"}, module)
        for forbidden in ["analysis", "core", "execution", "backend"]:
            self.assertFalse((ROOT / "ternfold" / forbidden).exists())

    def test_exact_seven_arithmetic_nine_boolean_and_prefixes(self):
        result = scan(" ".join(ARITHMETIC + BOOLEAN))
        self.assertEqual(
            [t.kind.value for t in result.tokens[:-1]],
            [
                "PLUS",
                "MINUS",
                "SLASH",
                "STAR",
                "PERCENT",
                "DIV",
                "CARET",
                "AND_AND",
                "OR_OR",
                "BANG",
                "GREATER",
                "LESS",
                "EQUAL_EQUAL",
                "BANG_EQUAL",
                "GREATER_EQUAL",
                "LESS_EQUAL",
            ],
        )
        self.assertEqual([t.lexeme for t in result.tokens[:-1]], ARITHMETIC + BOOLEAN)
        self.assertEqual(
            [
                t.lexeme
                for t in scan("!=! >= > <= < div dividend +++ ->- =>= :: : &&& |||").tokens[:-1]
            ],
            [
                "!=",
                "!",
                ">=",
                ">",
                "<=",
                "<",
                "div",
                "dividend",
                "++",
                "+",
                "->",
                "-",
                "=>",
                "=",
                "::",
                ":",
                "&&",
                "&",
                "||",
                "|",
            ],
        )
        for t in result.tokens[:-1]:
            self.assertEqual(t.span.text, t.lexeme)
            self.assertGreater(t.span.end_byte, t.span.start_byte)

    def test_literal_dfa_valid_invalid_and_numeric_boundaries(self):
        result = scan("17 0 true false \"hello\" 'Ω' 1.25e-2")
        self.assertEqual(
            [t.kind.value for t in result.tokens[:-1]],
            ["INT", "INT", "TRUE", "FALSE", "TEXT", "CHAR", "FLOAT"],
        )
        for text in ["00", "01e2", "1e+", "1e-", "1.2.3", "1e999foo", "12abc"]:
            with self.subTest(text=text):
                bad = scan(text)
                self.assertEqual(
                    [(t.kind.value, t.lexeme) for t in bad.tokens[:-1]], [("INVALID", text)]
                )
                self.assertEqual(bad.diagnostics.diagnostics[0].code, "E102")
        self.assertEqual(
            [t.kind.value for t in scan("1.foo 1.2.foo .5 1.").tokens[:-1]],
            ["INT", "DOT", "IDENT", "FLOAT", "DOT", "IDENT", "DOT", "INT", "INT", "DOT"],
        )
        self.assertFalse(
            scan("1e999 " + "9" * 10000).diagnostics.has_errors
        )  # semantic range is not lexing
        for text, code in [('"bad\\q"', "E103"), ("'ab'", "E105"), ("''", "E105"), ("@", "E101")]:
            self.assertEqual(scan(text).diagnostics.diagnostics[0].code, code)

    def test_comments_noise_delimiters_and_actual_two_column_order(self):
        text = (
            'input name: Text from stdin; output "Ω" to stdout;\r\n'
            "// one\r\n/* two\nlines */ let x=1;()[]{}"
        )
        result = scan(text)
        table = classroom_report(result)
        self.assertEqual(table.splitlines()[0], "TOKEN TYPE\tLEXEME")
        rows = [line.split("\t") for line in table.splitlines()[1:]]
        self.assertTrue(all(len(row) == 2 for row in rows))
        categories = [row[0] for row in rows]
        self.assertEqual(categories.count("NOISE_WORD"), 2)
        self.assertIn("LINE_COMMENT", categories)
        self.assertIn("BLOCK_COMMENT", categories)
        self.assertIn("ASSIGN", categories)
        self.assertIn("SEMICOLON", categories)
        spans = sorted(
            [t.span for t in result.tokens[:-1]]
            + [t.span for t in result.trivia if t.kind.value != "WHITESPACE"],
            key=lambda s: s.start_byte,
        )
        self.assertEqual([json.loads(row[1]) for row in rows], [s.text for s in spans])
        self.assertNotIn("UNIT_LITERAL", categories)
        self.assertNotIn(
            "NOISE_WORD",
            [
                line.split("\t")[0]
                for line in classroom_report(scan("from to input x:Text to stdout;")).splitlines()[
                    1:
                ]
            ],
        )
        self.assertEqual([x.lexeme for x in scan("/* a /* b */x//eof").tokens[:-1]], ["x"])
        self.assertEqual(scan("/*open").diagnostics.diagnostics[0].code, "E104")

    def test_invalid_recovery_progress_diagnostic_caps_and_coordinates(self):
        result = scan('"ñ"\r\n' + "@ " * 150)
        self.assertEqual(len(result.diagnostics.diagnostics), 100)
        self.assertEqual(result.diagnostics.suppressed[0].error_count, 50)
        self.assertEqual(classroom_report(result).count("INVALID\t"), 150)
        self.assertIsInstance(result.for_parser(), ErrorResult)
        self.assertIsInstance(scan("@", 0).for_parser(), ErrorResult)
        first = result.tokens[1].span
        self.assertEqual((first.start_byte, first.start.line, first.start.column), (6, 2, 1))
        self.assertEqual(
            [t.lexeme for t in scan('@ 09 "bad\\q"; let ok=1;').tokens[:-1]],
            ["@", "09", '"bad\\q"', ";", "let", "ok", "=", "1", ";"],
        )

    def test_actual_cli_valid_invalid_extension_encoding_and_golden_bytes(self):
        with tempfile.TemporaryDirectory(prefix="ternfold-lexical-test-") as directory:
            out = Path(directory)
            for filename, status in [("complete.tfd", 0), ("invalid.tfd", 1)]:
                result = command(ROOT / "examples" / filename, out)
                self.assertEqual(result.returncode, status, result.stderr)
                data = (out / "Symbol Table.txt").read_bytes()
                self.assertEqual(data, (ROOT / "expected" / (filename + ".txt")).read_bytes())
                self.assertFalse(data.startswith(b"\xef\xbb\xbf"))
                self.assertNotIn(b"\r", data)
            before = (out / "Symbol Table.txt").read_bytes()
            for name in ["wrong.txt", "wrong.TFD", "noextension"]:
                result = command(out / name, out)
                self.assertEqual(result.returncode, 2)
                self.assertEqual((out / "Symbol Table.txt").read_bytes(), before)
            for data, code in [
                (b"\xff", b"E001"),
                (b"\xef\xbb\xbflet", b"E002"),
                (b"let\r", b"E003"),
            ]:
                path = out / "raw.tfd"
                path.write_bytes(data)
                result = command(path, out)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(code, result.stderr)
                self.assertEqual((out / "Symbol Table.txt").read_bytes(), b"TOKEN TYPE\tLEXEME\n")
            path = out / "valid.tfd"
            path.write_text("let x=1;", encoding="utf-8")
            results = [
                command(path, out, PYTHONHASHSEED=seed, PYTHONINTMAXSTRDIGITS="640")
                for seed in ["1", "42"]
            ]
            self.assertTrue(all(r.returncode == 0 for r in results))
            result = command(ROOT / "examples/complete.tfd", out)
            self.assertEqual(
                (ROOT / "Symbol Table.txt").read_bytes(), (out / "Symbol Table.txt").read_bytes()
            )

    def test_seeded_character_progress_and_exact_byte_partition(self):
        rng = random.Random(2811)
        alphabet = "abc_01eE.+-/*<>=!&|;{}[]()\\\"' @\t\nΩñ"
        for case in range(250):
            text = "".join(rng.choice(alphabet) for _ in range(rng.randrange(150)))
            result = scan(text)
            spans = sorted(
                [t.span for t in result.tokens[:-1]] + [t.span for t in result.trivia],
                key=lambda s: s.start_byte,
            )
            cursor = 0
            for span in spans:
                self.assertEqual(span.start_byte, cursor, (case, text))
                self.assertGreater(span.end_byte, span.start_byte)
                cursor = span.end_byte
            self.assertEqual(cursor, len(text.encode("utf-8")))
            self.assertEqual(result.tokens[-1].kind, TokenKind.EOF)

    def test_report_cannot_replace_hardlinked_source(self):
        with tempfile.TemporaryDirectory(prefix="ternfold-hardlink-") as directory:
            out = Path(directory)
            source = out / "source.tfd"
            source.write_text("let value=1;", encoding="utf-8")
            os.link(source, out / "Symbol Table.txt")
            result = command(source, out)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(source.read_text(encoding="utf-8"), "let value=1;")

    def test_closed_stdout_and_stderr_are_host_two_without_shutdown_retry(self):
        with tempfile.TemporaryDirectory(prefix="ternfold-closed-pipe-") as directory:
            for filename, closed in [("complete.tfd", "stdout"), ("invalid.tfd", "stderr")]:
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-B",
                        "-S",
                        str(ROOT / "analyzer.py"),
                        str(ROOT / "examples" / filename),
                        "--output-dir",
                        directory,
                    ],
                    cwd=ROOT,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                pipe = getattr(process, closed)
                pipe.close()
                other = process.stderr if closed == "stdout" else process.stdout
                output = other.read()
                other.close()
                self.assertEqual(process.wait(timeout=15), 2, output)
                self.assertNotIn(b"Traceback", output)
                self.assertNotIn(b"Exception ignored", output)

    def test_demo_covers_every_inventory_and_literal_category(self):
        result = scan((ROOT / "examples/complete.tfd").read_text(encoding="utf-8"))
        self.assertFalse(result.diagnostics.has_errors)
        spellings = {t.lexeme for t in result.tokens}
        self.assertTrue(set(KEYWORDS + RESERVED + ARITHMETIC + BOOLEAN) <= spellings)
        rows = classroom_report(result).splitlines()[1:]
        categories = {row.split("\t")[0] for row in rows}
        self.assertTrue(
            {
                "INT_LITERAL",
                "FLOAT_LITERAL",
                "BOOL_LITERAL",
                "TEXT_LITERAL",
                "CHAR_LITERAL",
                "LINE_COMMENT",
                "BLOCK_COMMENT",
                "NOISE_WORD",
                "RESERVED_WORD",
                "IDENTIFIER",
            }
            <= categories
        )


if __name__ == "__main__":
    unittest.main()
