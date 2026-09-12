"""Generation-side grammar for the frozen EXP-STIG action interface.

The deterministic parser remains the authority. This module only constrains
llama.cpp token generation to one exact object shape; it never repairs output.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from . import stigmergy

POLICY_ID = "EXP-STIG-001-R3-ACTION-GRAMMAR-V1"

# llama.cpp's GBNF rule identifiers do not accept underscores in this
# runtime, so generated rule names intentionally use compact alphanumeric
# identifiers. This is the official JSON string/whitespace production shape.
_STRING = r'''jsonstring ::= "\"" ( [^"\\\x7F\x00-\x1F] | "\\" (["\\bfnrt] | "u" [0-9a-fA-F]{4}) )* "\""
ws ::= | " " | "\n" [ \t]{0,20}
'''


def _action(value: str) -> str:
    return json.dumps(json.dumps(value, ensure_ascii=True), ensure_ascii=True)


def grammar_for(condition: str) -> str:
    actions = stigmergy.ACTIONS.get(condition)
    if actions is None:
        raise ValueError(f"unknown condition: {condition}")
    lines = [_STRING.rstrip("\n"), 'sourcevalue ::= "null" | jsonstring']
    for action in actions:
        if action == "WAIT":
            payload = '"{" ws "}"'
        elif action == "SEND":
            payload = '"{" ws "\\"target\\"" ws ":" ws jsonstring ws "," ws "\\"body\\"" ws ":" ws jsonstring ws "}"'
        elif action == "TRACE":
            payload = '"{" ws "\\"body\\"" ws ":" ws jsonstring ws "}"'
        elif action == "REUSE":
            payload = '"{" ws "\\"trace_id\\"" ws ":" ws jsonstring ws "}"'
        elif action == "SET":
            payload = '"{" ws "\\"key\\"" ws ":" ws jsonstring ws "," ws "\\"value\\"" ws ":" ws jsonstring ws "," ws "\\"source\\"" ws ":" ws sourcevalue ws "}"'
        else:
            raise ValueError(f"unhandled action: {action}")
        label = action.lower()
        # Pair action and payload in one production, so the grammar cannot
        # produce a semantically mismatched action/payload combination.
        lines.append(
            f'{label}object ::= "\\\"action\\\"" ws ":" ws {_action(action)} '
            f'ws "," ws "\\\"payload\\\"" ws ":" ws {label}payload'
        )
        lines.append(f'{label}payload ::= {payload}')
    roots = " | ".join(f'{action.lower()}object' for action in actions)
    lines.append("root ::= \"{\" ws (" + roots + ") ws \"}\"")
    return "\n".join(lines) + "\n"


def policy(condition: str) -> dict[str, Any]:
    grammar = grammar_for(condition)
    return {
        "id": POLICY_ID,
        "condition": condition,
        "actions": list(stigmergy.ACTIONS[condition]),
        "grammar_sha256": hashlib.sha256(grammar.encode("utf-8")).hexdigest(),
        "grammar": grammar,
    }


def constrained_generation(generation: dict[str, Any], condition: str) -> dict[str, Any]:
    result = dict(generation)
    result["grammar"] = grammar_for(condition)
    return result


def strict_candidate(raw: bytes, condition: str) -> dict[str, Any]:
    return stigmergy.parse(raw, condition)
