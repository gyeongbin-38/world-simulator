from __future__ import annotations

import os
from pathlib import Path
from threading import Thread

import pytest

from alifelm.observatory.evidence import EvidenceBundle
from alifelm.observatory.projection import Observatory
from alifelm.observatory.server import ObservationServer


@pytest.fixture(scope="session")
def sealed_bundle(tmp_path_factory):
    source = os.environ.get("WORLD_OBSERVATORY_DATA_ROOT")
    if not source:
        pytest.skip("Real evidence requires WORLD_OBSERVATORY_DATA_ROOT; never replace it with fabricated data")
    return EvidenceBundle.open(Path(source), tmp_path_factory.mktemp("observation-cache"))


@pytest.fixture(scope="session")
def observation(sealed_bundle):
    return Observatory(sealed_bundle)


@pytest.fixture
def http_server(observation, tmp_path):
    (tmp_path / "index.html").write_text("<title>Observation test</title>")
    server = ObservationServer(("127.0.0.1", 0), observation, tmp_path)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
