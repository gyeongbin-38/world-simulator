import { useCallback, useEffect, useState } from "react";
import { getJSON } from "./types";
import type { Event, Frame, Run, View } from "./types";
import { Icon, OrbitMark, StatusPanel } from "./components/Shared";
import { LineageGraph, WorldGraph, WorldMetrics } from "./components/Graphs";
import { Timeline } from "./components/Timeline";
import { AgentInspector } from "./components/Inspector";
import { EvidenceDialog, EvidencePanel } from "./components/Evidence";
import { ReplayControls } from "./components/Replay";

const views: View[] = ["Overview", "World", "Lineage", "Timeline", "Evidence"];
const initialParams = new URLSearchParams(location.search);
const initialTick = Number(initialParams.get("tick") ?? 0);
const initialView =
  views.find((v) => v === initialParams.get("view")) ?? "Overview";

export default function App() {
  const [run, setRun] = useState<Run | null>(null);
  const [boot, setBoot] = useState<"loading" | "ready" | "empty" | "error">(
    "loading",
  );
  const [bootError, setBootError] = useState("");
  const [view, setView] = useState<View>(initialView);
  const [tick, setTick] = useState(
    Number.isInteger(initialTick) && initialTick >= 0 ? initialTick : 0,
  );
  const [frame, setFrame] = useState<Frame | null>(null);
  const [frameError, setFrameError] = useState("");
  const [selected, setSelected] = useState<string | null>(
    initialParams.get("agent"),
  );
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [raw, setRaw] = useState<{ ref: string; fullRun: boolean } | null>(
    null,
  );
  const base = run ? `/api/runs/${encodeURIComponent(run.id)}` : "";
  const current = frame?.tick === tick ? frame : null;
  const busy = !current;
  const selectedAgent = current?.agents.find((a) => a.id === selected);

  useEffect(() => {
    const controller = new AbortController();
    getJSON<{ runs: Run[] }>("/api/runs", controller.signal)
      .then(({ runs }) => {
        if (!runs.length) {
          setBoot("empty");
          return;
        }
        setRun(runs[0]);
        setTick((t) => Math.min(t, runs[0].horizon));
        setBoot("ready");
      })
      .catch((e) => {
        if (!controller.signal.aborted) {
          setBootError(e.message);
          setBoot("error");
        }
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!base) return;
    const controller = new AbortController();
    setFrameError("");
    getJSON<Frame>(`${base}/ticks/${tick}`, controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        if (data.tick !== tick || data.run_id !== run?.id)
          throw new Error("Integrity Conflict: observation identity mismatch");
        setFrame(data);
        setSelected((id) => (data.agents.some((a) => a.id === id) ? id : null));
      })
      .catch((e) => {
        if (!controller.signal.aborted) {
          setFrameError(e.message);
          setPlaying(false);
        }
      });
    return () => controller.abort();
  }, [base, tick, run?.id]);

  const seek = useCallback(
    (next: number) => {
      if (!run || !Number.isInteger(next)) return;
      setPlaying(false);
      setRaw(null);
      setTick(Math.max(0, Math.min(run.horizon, next)));
    },
    [run],
  );
  const play = useCallback(() => {
    if (raw || boot !== "ready") return;
    if (tick === run?.horizon) setTick(0);
    setPlaying((p) => !p);
  }, [raw, boot, tick, run?.horizon]);

  useEffect(() => {
    if (!playing || busy || !run) return;
    if (tick >= run.horizon) {
      setPlaying(false);
      return;
    }
    const timer = window.setTimeout(() => {
      setRaw(null);
      setTick((t) => Math.min(t + 1, run.horizon));
    }, 1500 / speed);
    return () => window.clearTimeout(timer);
  }, [playing, busy, tick, run, speed]);

  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (
        raw ||
        e.altKey ||
        e.ctrlKey ||
        e.metaKey ||
        (e.target instanceof HTMLElement &&
          (e.target.matches(
            'input, select, textarea, button, summary, a, [role="button"]',
          ) ||
            e.target.isContentEditable))
      )
        return;
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        seek(tick - 1);
      }
      if (e.key === "ArrowRight") {
        e.preventDefault();
        seek(tick + 1);
      }
      if (e.code === "Space") {
        e.preventDefault();
        play();
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [tick, seek, play, raw]);

  useEffect(() => {
    if (boot !== "ready") return;
    const params = new URLSearchParams({ tick: String(tick), view });
    if (selected) params.set("agent", selected);
    history.replaceState(null, "", `?${params}`);
  }, [tick, view, selected, boot]);

  const inspect = (id: string) => {
    setSelected(id);
    setPlaying(false);
  };
  const showEvidence = (ref: string, fullRun = false) => {
    setPlaying(false);
    setRaw({ ref, fullRun });
  };
  const eventSelected = (e: Event) => {
    seek(e.tick);
    if (e.agent_ids.length) setSelected(e.agent_ids[0]);
    if (view === "Timeline") setView("World");
  };
  const changeView = (next: View) => {
    setView(next);
    setRaw(null);
  };
  const headline =
    view === "Lineage"
      ? "Life continues."
      : view === "Timeline"
        ? "Every moment, recorded."
        : view === "Evidence"
          ? "Observation, with proof."
          : "A world, unfolding.";
  const subtitle =
    view === "Lineage"
      ? "Trace the relationships that carry a world forward."
      : view === "Timeline"
        ? "Follow what was attempted, and what became part of the world."
        : view === "Evidence"
          ? "From the visible world to the exact evidence behind it."
          : "A window into the lives and interactions of an artificial world.";

  return (
    <div className="observatory-shell">
      <a className="skip-link" href="#main">
        Skip to observation
      </a>
      <header className="topbar">
        <a className="brand" href="/?tick=0" aria-label="Observatory home">
          <OrbitMark />
          <span>Observatory</span>
        </a>
        <nav aria-label="Primary navigation">
          {views.map((v) => (
            <button
              key={v}
              className={view === v ? "active" : ""}
              aria-current={view === v ? "page" : undefined}
              onClick={() => changeView(v)}
            >
              {v}
            </button>
          ))}
        </nav>
        <span className="readonly-label">
          <Icon name="lock" size={14} />
          Read-only
        </span>
      </header>
      {boot === "loading" && (
        <StatusPanel title="Opening the Observatory…">
          Loading the preserved run and its observation identity.
        </StatusPanel>
      )}
      {boot === "empty" && (
        <StatusPanel title="A world is waiting to be observed.">
          No preserved run is configured. Set WORLD_OBSERVATORY_DATA_ROOT to the
          directory containing the sealed EXP-000 archive, then restart the
          observation server.
        </StatusPanel>
      )}
      {boot === "error" && (
        <StatusPanel
          title={
            bootError.includes("Integrity Conflict")
              ? "Integrity Conflict"
              : "Unable to open the Observatory"
          }
          error
        >
          {bootError}
        </StatusPanel>
      )}
      {boot === "ready" && run && (
        <>
          <main id="main" className="main-content">
            <div className="run-header">
              <div>
                <div className="run-kicker">
                  <span className="experiment-tag">EXP–000</span>
                  <span>ARTIFICIAL LIFE</span>
                  <i />
                  <span>SEALED REPLAY</span>
                </div>
                <h1>{headline}</h1>
                <p>{subtitle}</p>
              </div>
              <div className="observation-marker">
                <span className="eyebrow">OBSERVING</span>
                <strong data-testid="selected-tick">
                  {tick.toString().padStart(2, "0")}
                  <span> / {run.horizon}</span>
                </strong>
                <span>
                  {tick === run.horizon
                    ? "Final boundary"
                    : "After closing tick"}
                </span>
              </div>
            </div>
            {frameError ? (
              <StatusPanel title="Observation unavailable" error>
                {frameError}
              </StatusPanel>
            ) : !current ? (
              <div
                className="frame-loading"
                role="status"
                aria-label={`Loading tick ${tick}`}
              >
                <div className="loading-line" />
                <p>Reading tick {tick}…</p>
                <div className="loading-world">
                  <OrbitMark />
                </div>
              </div>
            ) : (
              <>
                {(view === "Overview" || view === "World") && (
                  <WorldMetrics frame={current} />
                )}
                <div
                  className={`workspace ${selectedAgent && view !== "Evidence" ? "with-inspector" : ""} ${view === "Overview" && !selectedAgent ? "with-activity" : ""}`}
                >
                  {(view === "Overview" || view === "World") && (
                    <WorldGraph
                      frame={current}
                      selected={selected}
                      onSelect={inspect}
                      expanded={view === "World"}
                      onExpand={() =>
                        changeView(view === "World" ? "Overview" : "World")
                      }
                    />
                  )}
                  {view === "Overview" && !selectedAgent && (
                    <Timeline
                      frame={current}
                      compact
                      onEvent={eventSelected}
                      onAll={() => changeView("Timeline")}
                    />
                  )}
                  {view === "Lineage" && (
                    <LineageGraph
                      frame={current}
                      selected={selected}
                      onSelect={inspect}
                    />
                  )}
                  {view === "Timeline" && (
                    <Timeline frame={current} onEvent={eventSelected} />
                  )}
                  {view === "Evidence" && (
                    <EvidencePanel
                      key={current.tick}
                      frame={current}
                      base={base}
                      onEvidence={showEvidence}
                    />
                  )}
                  {selectedAgent && view !== "Evidence" && (
                    <AgentInspector
                      key={`${selectedAgent.id}:${tick}`}
                      agent={selectedAgent}
                      frame={current}
                      onClose={() => setSelected(null)}
                      onSelect={inspect}
                      onEvidence={showEvidence}
                    />
                  )}
                </div>
                {(view === "Overview" || view === "World") && (
                  <div className="observation-summary">
                    <div>
                      <span className="summary-dot" />
                      <strong>
                        {current.tick === run.horizon
                          ? "The recorded horizon is complete."
                          : current.agents.some((a) => a.lifecycle === "born")
                            ? "A new life enters the world."
                            : current.attempts.some(
                                  (a) => a.tick === tick && !a.law_admitted,
                                )
                              ? "Not every attempt becomes an interaction."
                              : "Each tick leaves a trace."}
                      </strong>
                      <span>
                        {current.tick === run.horizon
                          ? "No post-horizon actions are recorded."
                          : current.agents.some((a) => a.lifecycle === "born")
                            ? "Birth and cognitive activation happen at different ticks."
                            : "Explore an agent to follow its recorded actions."}
                      </span>
                    </div>
                    <button
                      className="text-button"
                      onClick={() => changeView("Evidence")}
                    >
                      Follow the evidence <Icon name="arrow" size={13} />
                    </button>
                  </div>
                )}
                <div className="page-provenance">
                  <span>{run.id}</span>
                  <span>
                    Boundary S{current.boundary_tick} ·{" "}
                    {current.status.toLowerCase()} · locally verified
                  </span>
                </div>
              </>
            )}
          </main>
          <ReplayControls
            tick={tick}
            horizon={run.horizon}
            playing={playing}
            busy={busy}
            speed={speed}
            onSeek={seek}
            onPlay={play}
            onSpeed={setSpeed}
          />
          {raw && (
            <EvidenceDialog
              key={`${raw.ref}:${tick}`}
              base={base}
              reference={raw.ref}
              tick={tick}
              fullRun={raw.fullRun}
              onClose={() => setRaw(null)}
            />
          )}
        </>
      )}
    </div>
  );
}
