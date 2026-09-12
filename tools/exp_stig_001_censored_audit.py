"""Audit censored EXP-STIG evidence without interpreting agent action contents."""
from pathlib import Path
import argparse
import hashlib
import json
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from alifelm.experiments import stigmergy as s


def audit(root):
    planned = json.loads((root / "planned.json").read_bytes())
    failure = json.loads((root / "failure.json").read_bytes())
    assert failure["status"] == "INCOMPLETE_INVALID"
    assert failure["planned_digest"] == planned["manifest_digest"]
    assert not (root / "result.json").exists(), "a censored run cannot have a COMPLETE result"
    assert planned["manifest_digest"] == s.digest({k:v for k,v in planned.items() if k != "manifest_digest"})
    objects = {}
    for path in (root / "cas").glob("[0-9a-f][0-9a-f]/*"):
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == path.name
        objects[path.name] = data
    for name, value in planned["sources"].items():
        assert value in objects, name
    prepared, responses = [], []
    for value, data in objects.items():
        try:
            record = json.loads(data)
        except (ValueError, UnicodeError):
            continue
        if isinstance(record, dict) and {"actor", "model", "opportunity", "state_hash", "raw_ref"} <= record.keys():
            assert s.digest(record) == value
            for key in ("context_ref", "raw_ref", "response_ref"):
                assert record[key] in objects
            prepared.append(record)
        if isinstance(record, dict) and "generation_settings" in record:
            responses.append(record)
    assert len({a["opportunity"] for a in prepared}) == len(prepared)
    db = sqlite3.connect((root / "world.sqlite").as_uri() + "?mode=ro", uri=True)
    runs = db.execute("SELECT state,hash FROM stig_runs").fetchall()
    commits = db.execute("SELECT COUNT(*) FROM stig_commits").fetchone()[0]
    outbox = db.execute("SELECT COUNT(*) FROM stig_outbox").fetchone()[0]
    for data, expected in runs:
        assert s.digest(json.loads(data)) == expected
    db.close()
    # This particular censored execution stopped before its first all-agent barrier.
    assert commits == outbox == 0
    assert all(json.loads(data)["tick"] == 0 for data, _ in runs)
    assert len(responses) == len(prepared)
    record = {"status": "CENSORED_NO_SCIENTIFIC_RESULT", "planned_digest": planned["manifest_digest"],
        "reason": failure["error"], "initial_worlds": len(runs), "commits": commits,
        "prepared_attempts": len(prepared), "complete_responses": len(responses),
        "verified_CAS_objects": len(objects), "source_availability": True,
        "action_contents_scored": False, "S0_S3_label": None,
        "evidence_files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir()
             if p.is_file() and p.name != "censored-audit.json" and not p.name.endswith(("-wal", "-shm"))}}
    record["manifest_digest"] = s.digest(record)
    target = root / "censored-audit.json"
    data = s.encode(record)
    if target.exists():
        assert target.read_bytes() == data, "immutable audit mismatch"
    else:
        with target.open("xb") as output:
            output.write(data)
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    audit(parser.parse_args().output.resolve())
