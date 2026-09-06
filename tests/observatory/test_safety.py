from __future__ import annotations

from io import BytesIO
import hashlib
import json
from pathlib import Path
import sqlite3
import tarfile
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from alifelm.observatory.evidence import (
    ARCHIVE_SHA, MANIFEST_SHA, EvidenceError, IntegrityConflict, RUN_ID,
    discover, observation_connection, read_json, safe_extract, sha256, verify_file,
)


def test_discovery_verifies_actual_archive_and_preserves_source(sealed_bundle):
    assert discover(sealed_bundle.archive.parent) == [sealed_bundle.archive]
    assert sha256(sealed_bundle.archive) == ARCHIVE_SHA
    assert sha256(sealed_bundle.root / "manifest.json") == MANIFEST_SHA
    assert not sealed_bundle.cache.is_relative_to(sealed_bundle.archive.parent)


@pytest.mark.parametrize("statement", [
    "INSERT INTO agents_current SELECT run_id, 'UNAUTHORIZED', birth_tick, first_active_tick, lifespan_ticks, maturity_delay_ticks, state, refractory_until_tick FROM agents_current LIMIT 1",
    "UPDATE runs SET status='UNAUTHORIZED'",
    "DELETE FROM agents_current",
])
@pytest.mark.parametrize("query_only", [True, False])
def test_real_insert_update_delete_fail_even_without_query_only(sealed_bundle, statement, query_only):
    path = sealed_bundle.root / "run.sqlite"
    before = sha256(path)
    sidecars = {p.name: sha256(p) for p in path.parent.glob("run.sqlite*")}
    with observation_connection(path) as connection:
        assert connection.execute("SELECT count(*) FROM agents_current").fetchone()[0] == 2
        if not query_only:
            connection.execute("PRAGMA query_only=OFF")
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute(statement)
    assert sha256(path) == before
    assert {p.name: sha256(p) for p in path.parent.glob("run.sqlite*")} == sidecars


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:/absolute", "ok/../../escape", "ok\\..\\escape", "ok/file:stream", "ok/NUL", "ok/trailing."])
def test_archive_paths_rejected_before_any_extraction(tmp_path, name):
    archive = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive, "w:gz") as out:
        for file_name in ("good/file", name):
            member = tarfile.TarInfo(file_name)
            member.size = 3
            out.addfile(member, BytesIO(b"abc"))
    destination = tmp_path / "cache"
    destination.mkdir()
    with pytest.raises(EvidenceError):
        safe_extract(archive, destination)
    assert list(destination.iterdir()) == []


@pytest.mark.parametrize("kind", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE, tarfile.CHRTYPE])
def test_archive_links_and_special_files_rejected(tmp_path, kind):
    archive = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive, "w:gz") as out:
        member = tarfile.TarInfo("unsafe")
        member.type, member.linkname = kind, "../outside"
        out.addfile(member)
    destination = tmp_path / "cache"
    destination.mkdir()
    with pytest.raises(EvidenceError):
        safe_extract(archive, destination)


def test_archive_duplicate_case_paths_rejected(tmp_path):
    archive = tmp_path / "duplicate.tar.gz"
    with tarfile.open(archive, "w:gz") as out:
        for name in ("file", "FILE"):
            out.addfile(tarfile.TarInfo(name), BytesIO())
    cache = tmp_path / "cache"
    cache.mkdir()
    with pytest.raises(EvidenceError):
        safe_extract(archive, cache)


def test_missing_corrupt_and_live_db_are_not_repaired(tmp_path):
    missing = tmp_path / "missing"
    with pytest.raises(EvidenceError):
        verify_file(missing, ARCHIVE_SHA)
    assert not missing.exists()
    broken = tmp_path / "broken.json"
    broken.write_bytes(b"not json")
    with pytest.raises(EvidenceError):
        read_json(broken)
    with pytest.raises(IntegrityConflict):
        verify_file(broken, ARCHIVE_SHA)
    database = tmp_path / "fake.sqlite"
    database.write_bytes(b"fake")
    Path(str(database) + "-wal").write_bytes(b"uncheckpointed")
    with pytest.raises(EvidenceError, match="checkpointed"):
        with observation_connection(database):
            pytest.fail("A nonempty WAL must never be silently ignored")


def test_safe_extraction_exact_bytes(tmp_path):
    archive = tmp_path / "safe.tar.gz"
    data = b"exact evidence\x00\xff"
    with tarfile.open(archive, "w:gz") as out:
        member = tarfile.TarInfo("run/data.bin")
        member.size = len(data)
        out.addfile(member, BytesIO(data))
    cache = tmp_path / "cache"
    cache.mkdir()
    safe_extract(archive, cache)
    assert (cache / "run/data.bin").read_bytes() == data


def test_cached_attempt_bytes_must_still_match_authenticated_archive(tmp_path, monkeypatch):
    from alifelm.observatory import evidence

    archive = tmp_path / "sealed.tar.gz"
    original = b'{"score":1}'
    with tarfile.open(archive, "w:gz") as out:
        member = tarfile.TarInfo("run/evidence/attempt.json")
        member.size = len(original)
        out.addfile(member, BytesIO(original))
    monkeypatch.setattr(evidence, "ARCHIVE_SHA", sha256(archive))
    cache = tmp_path / "cache"
    cache.mkdir()
    safe_extract(archive, cache)
    bundle = evidence.EvidenceBundle(cache / "run/evidence", archive, cache)
    assert bundle.verify_cache() == 1
    (bundle.root / "attempt.json").write_bytes(b'{"score":9}')
    with pytest.raises(IntegrityConflict, match="SHA-256 mismatch"):
        bundle.verify_cache()


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
@pytest.mark.parametrize("route", ["/overview?tick=15", "/ticks/16", "/advance", "/agents/EXP000_FOUNDER_A"])
def test_http_mutations_fail_without_effect(http_server, observation, method, route):
    before = observation.frame(20)
    url = f"http://127.0.0.1:{http_server.server_port}/api/runs/{RUN_ID}{route}"
    with pytest.raises(HTTPError) as error:
        urlopen(Request(url, method=method, data=b'{"tick":21}'), timeout=5)
    assert error.value.code == 405
    assert error.value.headers["Allow"] == "GET, HEAD, OPTIONS"
    assert "Read-only" in error.value.read().decode()
    assert observation.frame(20) == before


def test_http_get_head_options_and_temporal_routes(http_server):
    base = f"http://127.0.0.1:{http_server.server_port}"
    for method in ("GET", "HEAD", "OPTIONS"):
        with urlopen(Request(base + "/api/runs", method=method)) as response:
            assert response.status == (204 if method == "OPTIONS" else 200)
            assert response.headers["X-Content-Type-Options"] == "nosniff"
            if method == "HEAD":
                assert response.read() == b""
    run = base + "/api/runs/" + RUN_ID
    for path in ("/ticks/15", "/overview?tick=15", "/events?tick=15", "/lineage?tick=15", "/agents/EXP000_FOUNDER_B?tick=15"):
        with urlopen(run + path) as response:
            assert json.load(response)["tick"] == 15
    with urlopen(run + "/events?tick=16&category=rejection") as response:
        events = json.load(response)["events"]
        assert all(e["category"] == "rejection" and e["tick"] <= 16 for e in events)


@pytest.mark.parametrize("path,code", [
    ("/api/runs/no-such-run", 404),
    (f"/api/runs/{RUN_ID}/events", 400),
    (f"/api/runs/{RUN_ID}/ticks/21", 400),
    (f"/api/runs/{RUN_ID}/ticks/-1", 400),
    (f"/api/runs/{RUN_ID}/overview?tick=15&tick=16", 400),
    (f"/api/runs/{RUN_ID}/evidence/../../manifest.json?tick=20", 400),
    (f"/api/runs/{RUN_ID}/evidence/%2e%2e%5crun.sqlite?tick=20", 400),
    ("/%2e%2e/pyproject.toml", 400),
])
def test_invalid_routes_fail_safely(http_server, path, code):
    with pytest.raises(HTTPError) as error:
        urlopen(f"http://127.0.0.1:{http_server.server_port}{path}")
    assert error.value.code == code


def test_evidence_digest_scope_and_exact_raw_integer(observation):
    reference = observation.tick_refs[16]
    with pytest.raises(KeyError):
        observation.evidence(reference, 15)
    with pytest.raises(KeyError):
        observation.evidence(MANIFEST_SHA, 16)
    assert observation.evidence(MANIFEST_SHA, 16, True)["scope"] == "Full Run"
    raw = observation.evidence(reference, 16)
    assert hashlib.sha256(raw["content"].encode()).hexdigest() == reference
    numerator = json.loads(raw["content"])["cognition"][0]["uniform_numerator"]
    assert numerator > 2**53
    assert str(numerator) in raw["content"]
    with pytest.raises(EvidenceError):
        observation.evidence("../manifest.json", 16)
    with pytest.raises(KeyError):
        observation.evidence("0" * 64, 16)


def test_host_rebinding_rejected(http_server):
    request = Request(f"http://127.0.0.1:{http_server.server_port}/api/runs", headers={"Host": "untrusted.example"})
    with pytest.raises(HTTPError) as error:
        urlopen(request)
    assert error.value.code == 403
