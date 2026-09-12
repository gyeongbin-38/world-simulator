import json

import pytest

from alifelm.experiments import action_codec as codec
from alifelm.experiments import stigmergy as s


def raw(action, payload):
    return json.dumps({"action": action, "payload": payload}, ensure_ascii=False).encode()


@pytest.mark.parametrize(
    "condition,actions",
    [("A", ("WAIT", "SEND")), ("B", ("WAIT", "SEND", "TRACE", "REUSE")),
     ("C", ("WAIT", "SEND", "TRACE", "REUSE", "SET"))],
)
def test_policy_is_derived_from_frozen_actions_and_is_stable(condition, actions):
    first = codec.policy(condition)
    second = codec.policy(condition)
    assert first["actions"] == list(actions)
    assert first["id"] == codec.POLICY_ID
    assert first["grammar_sha256"] == second["grammar_sha256"]
    assert first["grammar"] == second["grammar"]
    assert "actor" not in first["grammar"]
    assert "opportunity" not in first["grammar"]
    assert "authority" not in first["grammar"]
    assert "unknown" not in first["grammar"]


def test_grammar_pairs_action_and_payload_and_has_single_root():
    grammar = codec.grammar_for("C")
    assert grammar.count("root ::=") == 1
    assert "root ::= \"{\" ws (waitobject | sendobject | traceobject | reuseobject | setobject) ws \"}\"" in grammar
    assert r'\"WAIT\"' in grammar
    assert "waitobject ::= " in grammar and "waitpayload ::= " in grammar
    assert "sendobject ::= " in grammar and "sendpayload ::= " in grammar
    assert "setobject ::= " in grammar and "setpayload ::= " in grammar


@pytest.mark.parametrize(
    "condition,candidate",
    [
        ("A", ("WAIT", {})),
        ("A", ("SEND", {"target": "X29", "body": "hello"})),
        ("B", ("TRACE", {"body": "trace"})),
        ("B", ("REUSE", {"trace_id": "T1"})),
        ("C", ("SET", {"key": "K17", "value": "v", "source": None})),
    ],
)
def test_strict_candidates_remain_authoritative(condition, candidate):
    action, payload = candidate
    assert codec.strict_candidate(raw(action, payload), condition) == {
        "action": action, "payload": payload
    }


@pytest.mark.parametrize(
    "condition,malformed",
    [
        ("A", b'{"action":"WAIT","payload":{}} trailing'),
        ("A", b'{"action":"WAIT","action":"SEND","payload":{}}'),
        ("A", b'{"action":"TRACE","payload":{}}'),
        ("A", b'{"action":"WAIT","payload":{},"actor":"X17"}'),
        ("C", b'{"action":"WAIT","payload":{}},{"action":"WAIT","payload":{}}'),
    ],
)
def test_strict_parser_still_rejects_malformed_or_hidden_fields(condition, malformed):
    with pytest.raises((ValueError, json.JSONDecodeError)):
        codec.strict_candidate(malformed, condition)


def test_constrained_generation_only_adds_generation_side_grammar():
    base = {"temperature": 0.0, "n_predict": 128, "seed": 17}
    constrained = codec.constrained_generation(base, "B")
    assert constrained["temperature"] == base["temperature"]
    assert constrained["n_predict"] == base["n_predict"]
    assert "grammar" in constrained
    assert base == {"temperature": 0.0, "n_predict": 128, "seed": 17}
