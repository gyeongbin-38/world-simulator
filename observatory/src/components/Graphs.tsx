import type { CSSProperties } from "react";
import { aliasFor, lifeLabel } from "../types";
import type { Agent, Frame } from "../types";
import { AgentGlyph, Icon } from "./Shared";

type Point = { x: number; y: number };
// Slot positions are presentation constants. No future node participates in layout.
const points: Point[] = [
  { x: 220, y: 85 },
  { x: 620, y: 85 },
  { x: 530, y: 275 },
  { x: 225, y: 260 },
  { x: 765, y: 265 },
];
function point(a: Agent): Point {
  return (
    points[a.slot] ?? {
      x: 100 + (a.slot % 5) * 165,
      y: 130 + Math.floor(a.slot / 5) * 150,
    }
  );
}

function GraphNode({
  a,
  p,
  selected,
  onSelect,
}: {
  a: Agent;
  p: Point;
  selected: boolean;
  onSelect: (id: string) => void;
}) {
  return (
    <g
      role="button"
      tabIndex={0}
      aria-label={`${a.alias}, ${lifeLabel(a)}`}
      aria-pressed={selected}
      className={`graph-node ${selected ? "selected" : ""} ${a.lifecycle}`}
      data-agent-id={a.id}
      transform={`translate(${p.x} ${p.y})`}
      onClick={() => onSelect(a.id)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          e.stopPropagation();
          onSelect(a.id);
        }
      }}
    >
      <title>
        {a.alias} · {lifeLabel(a)} · Select to inspect
      </title>
      <circle className="node-focus" r="43" />
      <foreignObject
        x="-36"
        y="-36"
        width="72"
        height="72"
        pointerEvents="none"
      >
        <AgentGlyph agent={a} size={72} />
      </foreignObject>
      {a.lifecycle === "born" && <circle className="birth-ring" r="39" />}
      <text y="61" className="node-name" textAnchor="middle">
        {a.alias}
      </text>
      <text y="81" className="node-state" textAnchor="middle">
        {a.lifecycle === "born"
          ? "Born · not active"
          : a.lifecycle === "dead"
            ? "Dead"
            : `Generation ${a.generation}`}
      </text>
    </g>
  );
}

function edgePath(a: Point, b: Point, bend: number) {
  const dx = b.x - a.x,
    dy = b.y - a.y,
    d = Math.hypot(dx, dy);
  return `M ${a.x + (dx / d) * 44} ${a.y + (dy / d) * 44} Q ${(a.x + b.x) / 2 - (dy / d) * bend} ${(a.y + b.y) / 2 + (dx / d) * bend} ${b.x - (dx / d) * 47} ${b.y - (dy / d) * 47}`;
}

export function WorldGraph({
  frame,
  selected,
  onSelect,
  expanded,
  onExpand,
}: {
  frame: Frame;
  selected: string | null;
  onSelect: (id: string) => void;
  expanded?: boolean;
  onExpand?: () => void;
}) {
  const agents = frame.agents.filter((a) => a.lifecycle !== "dead");
  const dead = frame.agents.filter((a) => a.lifecycle === "dead");
  const ids = new Set(agents.map((a) => a.id));
  const start = Math.max(0, Math.min(frame.tick, frame.boundary_tick - 1) - 2);
  const messages = frame.messages.filter(
    (m) =>
      m.committed_tick >= start &&
      ids.has(m.sender_id) &&
      ids.has(m.recipient_id),
  );
  const proposals = frame.proposals.filter(
    (p) =>
      p.created_tick >= start &&
      p.state === "PENDING" &&
      ids.has(p.proposer_id) &&
      ids.has(p.target_id),
  );
  const edgeMap = new Map<
    string,
    { source: string; target: string; kind: string; count: number }
  >();
  for (const m of messages) {
    const key = `message:${m.sender_id}:${m.recipient_id}`;
    const previous = edgeMap.get(key);
    edgeMap.set(key, {
      source: m.sender_id,
      target: m.recipient_id,
      kind: "message",
      count: (previous?.count ?? 0) + 1,
    });
  }
  for (const p of proposals) {
    const key = `proposal:${p.proposer_id}:${p.target_id}`;
    const previous = edgeMap.get(key);
    edgeMap.set(key, {
      source: p.proposer_id,
      target: p.target_id,
      kind: "proposal",
      count: (previous?.count ?? 0) + 1,
    });
  }
  const edges = [...edgeMap.values()];
  const rejected = frame.attempts.filter(
    (a) => a.tick === frame.tick && !a.law_admitted,
  );
  return (
    <section
      className={`world-surface ${expanded ? "expanded" : ""}`}
      aria-label="Interaction view"
    >
      <div className="surface-heading">
        <div>
          <span className="eyebrow">THE OBSERVED WORLD</span>
          <h2>Interaction view</h2>
        </div>
        {onExpand && (
          <button
            className="icon-button"
            onClick={onExpand}
            aria-label={expanded ? "Return to overview" : "Expand world view"}
          >
            <Icon name="expand" />
          </button>
        )}
      </div>
      <div className="graph-legend">
        <span>
          <i className="legend-line message" />
          Message committed
        </span>
        <span>
          <i className="legend-line proposal" />
          Pending proposal
        </span>
        <span className="legend-window">
          Ticks {start}–{Math.min(frame.tick, frame.boundary_tick - 1)}
        </span>
      </div>
      <svg
        className="world-svg"
        viewBox="0 0 900 390"
        role="group"
        aria-label={`Interaction topology at tick ${frame.tick}`}
      >
        <defs>
          <marker
            id="message-arrow"
            viewBox="0 0 10 10"
            refX="8"
            refY="5"
            markerWidth="5"
            markerHeight="5"
            orient="auto-start-reverse"
          >
            <path d="M0 0 10 5 0 10Z" fill="#6b8799" />
          </marker>
          <marker
            id="proposal-arrow"
            viewBox="0 0 10 10"
            refX="8"
            refY="5"
            markerWidth="5"
            markerHeight="5"
            orient="auto-start-reverse"
          >
            <path d="M0 0 10 5 0 10Z" fill="#8e81a1" />
          </marker>
        </defs>
        {edges.map((edge) => {
          const a = point(agents.find((a) => a.id === edge.source)!),
            b = point(agents.find((a) => a.id === edge.target)!);
          return (
            <path
              key={`${edge.kind}:${edge.source}:${edge.target}`}
              className={`interaction-edge ${edge.kind}`}
              data-edge-kind={edge.kind}
              data-source={edge.source}
              data-target={edge.target}
              d={edgePath(a, b, edge.kind === "proposal" ? 32 : -24)}
              markerEnd={`url(#${edge.kind}-arrow)`}
            >
              <title>
                {aliasFor(frame, edge.source)} → {aliasFor(frame, edge.target)}{" "}
                · {edge.count}{" "}
                {edge.kind === "message"
                  ? "committed message(s)"
                  : "pending proposal(s)"}
              </title>
            </path>
          );
        })}
        {agents.map((a) => (
          <GraphNode
            key={a.id}
            a={a}
            p={point(a)}
            selected={selected === a.id}
            onSelect={onSelect}
          />
        ))}
      </svg>
      {rejected.length > 0 && (
        <div className="attempt-note">
          <Icon name="rejection" size={16} />
          <span>
            {rejected
              .map(
                (a) =>
                  `${aliasFor(frame, a.agent_id)} · ${a.selected_action} rejected by Law`,
              )
              .join(" / ")}
            <small>No canonical interaction edge created.</small>
          </span>
        </div>
      )}
      {dead.length > 0 && (
        <div className="remembered">
          <span>Recorded deaths</span>
          {dead.map((a) => (
            <button key={a.id} onClick={() => onSelect(a.id)}>
              {a.alias}
              <Icon name="arrow" size={12} />
            </button>
          ))}
        </div>
      )}
      <div className="graph-footnote">
        <span>
          Layout represents interaction topology, not physical position.
        </span>
        <span>{agents.length} living agents</span>
      </div>
    </section>
  );
}

export function LineageGraph({
  frame,
  selected,
  onSelect,
}: {
  frame: Frame;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const positions = new Map(
    frame.agents.map((a) => [
      a.id,
      a.generation === 0
        ? { x: 175 + a.slot * 265, y: 130 }
        : { x: 335 + (a.slot - 3) * 250, y: 370 },
    ]),
  );
  return (
    <section className="lineage-surface">
      <div className="surface-heading">
        <div>
          <span className="eyebrow">CANONICAL RELATIONSHIPS</span>
          <h2>Two parents. A next generation.</h2>
        </div>
        <span className="subtle-tag">Through tick {frame.tick}</span>
      </div>
      <p className="section-intro">
        Every connection begins with a recorded birth. Select a life to follow
        its evidence.
      </p>
      <svg
        viewBox="0 0 900 500"
        className="lineage-svg"
        role="group"
        aria-label="Two-parent lineage"
      >
        <text x="25" y="40" className="generation-label">
          GENERATION 0
        </text>
        {frame.lineage.length > 0 && (
          <text x="25" y="290" className="generation-label">
            GENERATION 1
          </text>
        )}
        {frame.lineage.map((birth, i) => {
          const child = positions.get(birth.child_id)!,
            p1 = positions.get(birth.parent_ids[0])!,
            p2 = positions.get(birth.parent_ids[1])!;
          const y = 253 + i * 28;
          return (
            <g
              key={birth.child_id}
              className="lineage-connection"
              data-child={birth.child_id}
              data-parents={birth.parent_ids.join(",")}
            >
              <path
                d={`M${p1.x} ${p1.y + 92} V${y} H${child.x} M${p2.x} ${p2.y + 92} V${y} H${child.x} M${child.x} ${y} V${child.y - 44}`}
              />
              <circle cx={child.x} cy={y} r="3" />
              <title>
                {birth.parent_ids.map((p) => aliasFor(frame, p)).join(" + ")} →{" "}
                {aliasFor(frame, birth.child_id)} · Birth tick{" "}
                {birth.birth_tick}
              </title>
              <text x={child.x + 10} y={child.y - 63}>
                Birth · tick {birth.birth_tick}
              </text>
            </g>
          );
        })}
        {frame.agents.map((a) => (
          <GraphNode
            key={a.id}
            a={a}
            p={positions.get(a.id)!}
            selected={selected === a.id}
            onSelect={onSelect}
          />
        ))}
      </svg>
      {frame.lineage.length === 0 && (
        <p className="lineage-empty">
          No children have been born by this tick.
        </p>
      )}
      <div className="graph-footnote">
        <span>
          Genealogy is a birth record. It does not imply social affinity or
          inherited experience.
        </span>
      </div>
    </section>
  );
}

export function WorldMetrics({ frame }: { frame: Frame }) {
  const values: [string, number, string][] = [
    ["Living agents", frame.metrics.population, "Population after this commit"],
    [
      "Generation depth",
      frame.metrics.generation,
      "From the founding generation",
    ],
    ["Births", frame.metrics.births, "Canonical births through this tick"],
    ["Natural deaths", frame.metrics.deaths, "Committed lifecycle boundaries"],
  ];
  return (
    <dl className="world-metrics">
      {values.map(([label, value, hint]) => (
        <div
          key={label}
          style={
            {
              "--metric-index": values.findIndex((v) => v[0] === label),
            } as CSSProperties
          }
        >
          <dt>{label}</dt>
          <dd
            data-testid={`metric-${label.toLowerCase().replaceAll(" ", "-")}`}
          >
            {value.toString().padStart(2, "0")}
          </dd>
          <span>{hint}</span>
        </div>
      ))}
    </dl>
  );
}
