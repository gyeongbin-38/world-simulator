import { aliasFor, lifeLabel, shortId } from "../types";
import type { Agent, Frame } from "../types";
import { AgentGlyph, CopyButton, Icon } from "./Shared";

export function AgentInspector({
  agent,
  frame,
  onClose,
  onSelect,
  onEvidence,
}: {
  agent: Agent;
  frame: Frame;
  onClose: () => void;
  onSelect: (id: string) => void;
  onEvidence: (ref: string) => void;
}) {
  const attempts = frame.attempts
    .filter((a) => a.agent_id === agent.id)
    .toReversed();
  const messages = frame.messages.filter(
    (m) => m.sender_id === agent.id || m.recipient_id === agent.id,
  );
  const proposals = frame.proposals.filter(
    (p) => p.proposer_id === agent.id || p.target_id === agent.id,
  );
  return (
    <aside className="agent-inspector" aria-label={`${agent.alias} Inspector`}>
      <div className="inspector-top">
        <span className="eyebrow">LIFE IN FOCUS · TICK {frame.tick}</span>
        <button
          className="icon-button"
          onClick={onClose}
          aria-label="Close Inspector"
        >
          <Icon name="close" />
        </button>
      </div>
      <div className="inspector-identity">
        <AgentGlyph agent={agent} size={80} />
        <h2>{agent.alias}</h2>
        <span className={`life-status ${agent.lifecycle}`}>
          {lifeLabel(agent)}
        </span>
      </div>
      <details className="identity-details">
        <summary>
          Canonical identity <Icon name="evidence" size={14} />
        </summary>
        <code className="canonical-id">{agent.id}</code>
        <CopyButton value={agent.id} />
      </details>
      <dl className="agent-facts">
        <div>
          <dt>Generation</dt>
          <dd>{agent.generation === 0 ? "Founder · 0" : agent.generation}</dd>
        </div>
        <div>
          <dt>Age</dt>
          <dd>{agent.age} active ticks</dd>
        </div>
        <div>
          <dt>Birth tick</dt>
          <dd>
            {agent.birth_tick}
            {agent.generation === 0 ? " · founder in S₀" : ""}
          </dd>
        </div>
        <div>
          <dt>First active tick</dt>
          <dd>{agent.first_active_tick}</dd>
        </div>
        {agent.death_tick !== null && (
          <>
            <div>
              <dt>Death commit tick</dt>
              <dd>{agent.death_commit_tick}</dd>
            </div>
            <div>
              <dt>Death boundary</dt>
              <dd>{agent.death_tick}</dd>
            </div>
          </>
        )}
      </dl>
      <p className="definition">
        Age counts completed active ticks at boundary S{frame.boundary_tick},
        capped at recorded death.
      </p>
      {agent.lifecycle === "born" && (
        <p className="lifecycle-note">
          Born in this commit. Cognition begins no earlier than tick{" "}
          {agent.first_active_tick}.
        </p>
      )}
      {!agent.has_cognition && agent.lifecycle !== "born" && (
        <p className="lifecycle-note">
          Eligible from tick {agent.first_active_tick}. No cognition is recorded
          for this agent within the run horizon.
        </p>
      )}
      <section className="inspector-section">
        <h3>Family</h3>
        {agent.parents.length > 0 ? (
          <>
            <span className="field-label">Two canonical parents</span>
            <div className="family-links">
              {agent.parents.map((id) => (
                <button key={id} onClick={() => onSelect(id)}>
                  {aliasFor(frame, id)}
                  <Icon name="arrow" size={12} />
                </button>
              ))}
            </div>
          </>
        ) : (
          <p className="muted">Founding generation</p>
        )}
        {agent.children.length > 0 && (
          <>
            <span className="field-label">Children by this tick</span>
            <div className="family-links">
              {agent.children.map((id) => (
                <button key={id} onClick={() => onSelect(id)}>
                  {aliasFor(frame, id)}
                  <Icon name="arrow" size={12} />
                </button>
              ))}
            </div>
          </>
        )}
      </section>
      <section className="inspector-section">
        <h3>
          Recorded actions <span>{attempts.length}</span>
        </h3>
        {!attempts.length && (
          <p className="muted">
            No recorded actions through tick {frame.tick}.
          </p>
        )}
        {attempts.slice(0, 6).map((a) => (
          <div
            key={a.id}
            className={`inspector-attempt ${a.law_admitted ? "" : "rejected"}`}
          >
            <div>
              <strong>{a.selected_action} attempted</strong>
              <span>Tick {a.tick}</span>
            </div>
            <p>{a.law_admitted ? "Admitted by Law" : "Rejected by Law"}</p>
            {a.target_id && (
              <small>
                {agent.alias} →{" "}
                {a.target_id === agent.id
                  ? `${agent.alias} (self)`
                  : aliasFor(frame, a.target_id)}
              </small>
            )}
            {!a.law_admitted && (
              <small>
                {a.selected_action === "SEND"
                  ? "No message committed"
                  : "No transition committed"}
              </small>
            )}
            <button
              className="text-button"
              onClick={() => onEvidence(a.evidence_ref)}
            >
              Inspect evidence <Icon name="arrow" size={12} />
            </button>
          </div>
        ))}
        {attempts.length > 6 && (
          <p className="definition">
            Showing the six most recent attempts. The Timeline contains the full
            history through this tick.
          </p>
        )}
      </section>
      <details className="inspector-section">
        <summary>
          Messages <span>{messages.length}</span>
        </summary>
        <p className="definition">
          Canonical committed text. Message content is model output, not a
          factual description of an agent.
        </p>
        {!messages.length && (
          <p className="muted">No messages committed for this agent.</p>
        )}
        {messages.toReversed().map((m) => (
          <div className="message-record" key={m.message_id}>
            <small>
              Tick {m.committed_tick} ·{" "}
              {m.sender_id === agent.id ? "Sent to" : "Received from"}{" "}
              {aliasFor(
                frame,
                m.sender_id === agent.id ? m.recipient_id : m.sender_id,
              )}
            </small>
            <blockquote>{m.body}</blockquote>
            <span className="definition">
              Peer-visible from tick {m.available_tick}
            </span>
          </div>
        ))}
      </details>
      <details className="inspector-section">
        <summary>
          Proposals <span>{proposals.length}</span>
        </summary>
        {!proposals.length && <p className="muted">No proposals recorded.</p>}
        {proposals.toReversed().map((p) => (
          <div className="proposal-record" key={p.proposal_id}>
            <strong>
              {aliasFor(frame, p.proposer_id)} → {aliasFor(frame, p.target_id)}
            </strong>
            <small>
              Created {p.created_tick} · {p.state.toLowerCase()}
            </small>
            <code>{shortId(p.proposal_id)}</code>
          </div>
        ))}
      </details>
    </aside>
  );
}
