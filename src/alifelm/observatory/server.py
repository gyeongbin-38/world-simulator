"""Loopback HTTP observation server. Only GET, HEAD and OPTIONS are supported."""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from .evidence import RUN_ID, EvidenceBundle, EvidenceError, IntegrityConflict
from .projection import Observatory

REPO_ROOT = Path(__file__).resolve().parents[3]


class ObservationServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, observatory: Observatory | None, static_root: Path, error: str | None = None):
        self.observatory = observatory
        self.static_root = static_root.resolve()
        self.evidence_error = error
        super().__init__(address, ObservationHandler)


class ObservationHandler(BaseHTTPRequestHandler):
    server: ObservationServer
    server_version = "Observatory/1"

    def _send(self, status: int, body: bytes, content_type: str = "application/json; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        if status == 405 or self.command == "OPTIONS":
            self.send_header("Allow", "GET, HEAD, OPTIONS")
        self.end_headers()
        if self.command != "HEAD":
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

    def _json(self, status: int, value):
        self._send(status, json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode())

    def do_OPTIONS(self):
        self._send(204, b"")

    def _mutation_denied(self):
        self.close_connection = True
        self._json(405, {"error": "Read-only Observatory. World mutations are not supported."})

    do_POST = do_PUT = do_PATCH = do_DELETE = do_TRACE = do_CONNECT = _mutation_denied

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        try:
            # Local UI only; also reject Host-based DNS rebinding.
            if self.headers.get("Host", "").split(":")[0].lower() not in ("127.0.0.1", "localhost", "[::1]"):
                return self._json(403, {"error": "Loopback host required"})
            parsed = urlsplit(self.path)
            path = unquote(parsed.path)
            if any(part in ("..", ".") for part in path.split("/")) or any(c in path for c in ("\\", "\x00", ":")):
                raise EvidenceError("Invalid request path")
            if path == "/health":
                return self._json(200 if self.server.observatory else 503,
                                  {"status": "ready" if self.server.observatory else "unavailable", "read_only": True})
            if path.startswith("/api/"):
                return self._api(path, parse_qs(parsed.query, keep_blank_values=True))
            relative = "index.html" if path == "/" else path.lstrip("/")
            target = (self.server.static_root / relative).resolve()
            if not target.is_relative_to(self.server.static_root) or not target.is_file():
                return self._json(404, {"error": "Not found. Build the Observatory frontend before launching."})
            self._send(200, target.read_bytes(), mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        except IntegrityConflict as exc:
            self._json(409, {"error": "Integrity Conflict", "detail": str(exc)})
        except EvidenceError as exc:
            self._json(400, {"error": str(exc)})
        except (ValueError, TypeError):
            self._json(400, {"error": "Invalid observation request"})
        except KeyError as exc:
            self._json(404, {"error": str(exc).strip("'")})
        except OSError:
            self._json(503, {"error": "Evidence is unavailable"})

    def _api(self, path: str, query: dict[str, list[str]]):
        if self.server.evidence_error:
            return self._json(409, {"error": "Integrity Conflict", "detail": self.server.evidence_error})
        obs = self.server.observatory
        if path == "/api/runs":
            return self._json(200, {"runs": [obs.summary()] if obs else []})
        if obs is None:
            return self._json(503, {"error": "No sealed evidence configured"})
        parts = path.strip("/").split("/")
        if len(parts) < 3 or parts[:2] != ["api", "runs"] or parts[2] != RUN_ID:
            raise KeyError("Unknown run")
        if len(parts) == 3:
            return self._json(200, obs.summary())
        if parts[3:] == ["integrity"]:
            return self._json(200, obs.integrity())
        if any(len(v) != 1 for v in query.values()):
            raise EvidenceError("Duplicate query parameter")
        if parts[3] == "ticks" and len(parts) == 5:
            return self._json(200, obs.frame(int(parts[4])))
        if "tick" not in query:
            raise EvidenceError("An explicit observation tick is required")
        tick = obs.validate_tick(int(query["tick"][0]))
        if parts[3:] == ["overview"]:
            return self._json(200, obs.frame(tick))
        if parts[3] == "agents" and len(parts) == 5:
            return self._json(200, obs.agent(parts[4], tick))
        if parts[3:] == ["events"]:
            events = obs.frame(tick)["events"]
            if "category" in query:
                events = [e for e in events if e["category"] == query["category"][0]]
            return self._json(200, {"tick": tick, "events": events})
        if parts[3:] == ["lineage"]:
            frame = obs.frame(tick)
            return self._json(200, {"tick": tick, "agents": frame["agents"], "births": frame["lineage"]})
        if parts[3] == "evidence" and len(parts) == 5:
            if query.get("scope", ["tick"])[0] not in ("tick", "full-run"):
                raise EvidenceError("Invalid evidence scope")
            return self._json(200, obs.evidence(parts[4], tick, query.get("scope") == ["full-run"]))
        raise KeyError("Unknown observation route")

    def log_message(self, format, *args):
        # No evidence contents, canonical IDs, or query parameters in access logs.
        pass


def main():
    parser = argparse.ArgumentParser(description="Read-only, sealed EXP-000 Observatory")
    parser.add_argument("--data-root", type=Path, default=os.environ.get("WORLD_OBSERVATORY_DATA_ROOT"))
    parser.add_argument("--cache-root", type=Path, default=REPO_ROOT / ".observatory-cache")
    parser.add_argument("--static-root", type=Path, default=REPO_ROOT / "observatory" / "dist")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    obs, error = None, None
    if args.data_root:
        try:
            obs = Observatory(EvidenceBundle.open(args.data_root, args.cache_root))
        except EvidenceError as exc:
            error = str(exc)
    server = ObservationServer(("127.0.0.1", args.port), obs, args.static_root, error)
    print(f"Observatory: http://127.0.0.1:{server.server_port} · read-only sealed replay", flush=True)
    if error:
        print("Integrity Conflict: " + error, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
