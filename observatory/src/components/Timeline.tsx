import { useState } from "react";
import type { Event, Frame } from "../types";
import { Icon } from "./Shared";

export function Timeline({
  frame,
  compact = false,
  onEvent,
  onAll,
}: {
  frame: Frame;
  compact?: boolean;
  onEvent: (e: Event) => void;
  onAll?: () => void;
}) {
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const events = frame.events.filter(
    (e) =>
      (!compact || e.category !== "action") &&
      (filter === "all" || filter === e.category) &&
      `${e.title} ${e.detail}`.toLowerCase().includes(search.toLowerCase()),
  );
  const shown = compact ? events.slice(0, 5) : events;
  const ticks = [...new Set(shown.map((e) => e.tick))];
  return (
    <section
      className={compact ? "activity-panel" : "timeline-page"}
      aria-label={compact ? "Recent activity" : "Timeline activity"}
    >
      <div className="surface-heading">
        <div>
          <span className="eyebrow">
            {compact ? "A CLOSER LOOK" : "THE RECORDED HISTORY"}
          </span>
          <h2>{compact ? "Recent activity" : "Life, tick by tick."}</h2>
        </div>
        <span className="quiet-count">
          {compact ? "↙" : `${events.length} records`}
        </span>
      </div>
      {!compact && (
        <>
          <p className="section-intro">
            Selections, rejections and committed events, through tick{" "}
            {frame.tick}. Peer attempts are grouped by tick, without an invented
            order.
          </p>
          <div className="timeline-filters">
            <label>
              Show
              <select
                aria-label="Event type"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
              >
                <option value="all">All activity</option>
                <option value="action">Action selections</option>
                <option value="message">Messages committed</option>
                <option value="proposal">Proposals</option>
                <option value="birth">Births</option>
                <option value="death">Natural deaths</option>
                <option value="rejection">Law rejections</option>
                <option value="run">Run transitions</option>
              </select>
            </label>
            <input
              type="search"
              aria-label="Search timeline"
              placeholder="Find an agent or event"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </>
      )}
      <div className="activity-feed">
        {ticks.map((tick) => (
          <div className="tick-group" key={tick}>
            <span className="tick-heading">
              TICK {tick.toString().padStart(2, "0")}
            </span>
            {shown
              .filter((e) => e.tick === tick)
              .map((e) => (
                <button
                  key={e.id}
                  className={`event-row ${e.category}`}
                  onClick={() => onEvent(e)}
                >
                  <span className="event-icon">
                    <Icon name={e.category} size={17} />
                  </span>
                  <span className="event-text">
                    <strong>{e.title}</strong>
                    <span>{e.detail}</span>
                    {!compact && (
                      <small>
                        {e.canonical ? "Canonical record" : "Action attempt"}
                        {e.record.commit_order !== undefined
                          ? ` · event ordinal ${e.record.commit_order}`
                          : ""}
                      </small>
                    )}
                  </span>
                  <Icon name="arrow" size={13} />
                </button>
              ))}
          </div>
        ))}
      </div>
      {!shown.length && (
        <div className="empty-state">
          <Icon name="action" size={25} />
          <p>No matching activity at or before this tick.</p>
        </div>
      )}
      {compact && (
        <button className="text-button activity-all" onClick={onAll}>
          Explore timeline <Icon name="arrow" size={14} />
        </button>
      )}
    </section>
  );
}
