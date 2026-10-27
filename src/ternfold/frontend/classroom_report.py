"""Two-column classroom adapter over the one production lexical result."""

import json

from ternfold.frontend.lexer import LexResult
from ternfold.frontend.lexical_report import symbol_rows


def classroom_report(result: LexResult) -> str:
    lines = ["TOKEN TYPE\tLEXEME"]
    categories = {
        "COMMENT_LINE": "LINE_COMMENT",
        "COMMENT_BLOCK": "BLOCK_COMMENT",
        "RESERVED_NAME": "RESERVED_WORD",
    }
    for row in symbol_rows(result):
        if row.view == "composite":
            continue  # Unit is two real bracket tokens, never a duplicate lexeme.
        category = categories.get(row.category, row.category)
        if category in {"OPERATOR", "DELIMITER"}:
            category = "ASSIGN" if row.kind == "EQUAL" else row.kind
        lines.append(category + "\t" + json.dumps(row.span.text, ensure_ascii=True))
    return "\n".join(lines) + "\n"
