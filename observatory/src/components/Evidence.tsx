import { useEffect, useRef, useState } from "react";
import { aliasFor, getJSON } from "../types";
import type { Frame, Integrity, RawEvidence } from "../types";
import { CopyButton, HashRow, Icon } from "./Shared";

export function EvidencePanel({
  frame,
  base,
  onEvidence,
}: {
  frame: Frame;
  base: string;
  onEvidence: (ref: string, fullRun?: boolean) => void;
}) {
  const [integrity, setIntegrity] = useState<Integrity | null>(null);
  const [error, setError] = useState("");
  const [agentFilter, setAgentFilter] = useState("all");
  useEffect(() => {
    const controller = new AbortController();
    getJSON<Integrity>(`${base}/integrity`, controller.signal)
      .then(setIntegrity)
      .catch((e) => {
        if (!controller.signal.aborted) setError(String(e.message));
      });
    return () => controller.abort();
  }, [base]);
  const attempts = frame.attempts.filter(
    (a) =>
      a.tick === frame.tick &&
      (agentFilter === "all" || a.agent_id === agentFilter),
  );
  return (
    <section className="evidence-page">
      <div className="evidence-intro">
        <span className="eyebrow">FOLLOW THE EVIDENCE</span>
        <h2>A clear line back to the source.</h2>
        <p>
          Recorded actions and canonical outcomes stay distinct. Every
          observation can be traced to the sealed run.
        </p>
      </div>
      <section className="evidence-boundary">
        <div>
          <span className="eyebrow">SELECTED OBSERVATION</span>
          <h3>
            Tick {frame.tick} <span>→</span> Boundary S{frame.boundary_tick}
          </h3>
          <p>
            {frame.mode} · State version {frame.state_version}
          </p>
        </div>
        {frame.evidence_ref && (
          <button
            className="secondary-button"
            onClick={() => onEvidence(frame.evidence_ref!)}
          >
            Open tick evidence <Icon name="arrow" size={14} />
          </button>
        )}
      </section>
      <details className="evidence-disclosure">
        <summary>
          Snapshot identity <span>Exact selected boundary</span>
        </summary>
        <HashRow label="State hash" value={frame.state_hash} />
        <HashRow label="Run ID" value={frame.run_id} />
        <p className="definition">
          Projection schema: {frame.projection_schema}. The observation cursor
          reads recorded commits; it never advances the world.
        </p>
      </details>
      <section className="cognition-evidence">
        <div className="section-heading">
          <h3>Decisions at tick {frame.tick}</h3>
          <label>
            <span className="sr-only">Filter evidence by agent</span>
            <select
              aria-label="Filter evidence by agent"
              value={agentFilter}
              onChange={(e) => setAgentFilter(e.target.value)}
            >
              <option value="all">All agents</option>
              {frame.agents.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.alias}
                </option>
              ))}
            </select>
          </label>
        </div>
        {!attempts.length && (
          <p className="empty-inline">
            {frame.tick === frame.boundary_tick
              ? "Final boundary. No post-horizon cognition exists."
              : "No action evidence for this selection."}
          </p>
        )}
        {attempts.map((a) => (
          <details className="decision-record" key={a.id}>
            <summary>
              <span>{aliasFor(frame, a.agent_id)}</span>
              <strong>{a.selected_action} selected</strong>
              <span
                className={a.law_admitted ? "admitted-label" : "rejected-label"}
              >
                {a.law_admitted ? "Admitted by Law" : "Rejected by Law"}
              </span>
            </summary>
            <p className="definition">
              Action selection is an attempt. Admission is not itself a
              committed message or birth.
            </p>
            <table className="scores-table">
              <caption>Recorded selector scores and probabilities</caption>
              <thead>
                <tr>
                  <th>Action</th>
                  <th>Score</th>
                  <th>Probability</th>
                </tr>
              </thead>
              <tbody>
                {Object.keys(a.score_vector).map((action) => (
                  <tr
                    key={action}
                    className={
                      action === a.selected_action ? "selected-score" : ""
                    }
                  >
                    <th>
                      {action}
                      {action === a.selected_action ? " · selected" : ""}
                    </th>
                    <td>{a.score_vector[action]}</td>
                    <td>{(a.probabilities[action] * 100).toFixed(3)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <h4>Gateway intent</h4>
            <pre>{JSON.stringify(a.gateway_intent, null, 2)}</pre>
            <p className="definition">Parse status: {a.parse_status}</p>
            {a.proposal_grounding && (
              <>
                <h4>Proposal handle grounding</h4>
                <p className="definition">
                  Recorded local handles resolved to canonical proposal
                  identities.
                </p>
                <pre>{JSON.stringify(a.proposal_grounding, null, 2)}</pre>
              </>
            )}
            <div className="evidence-actions">
              <button
                className="text-button"
                onClick={() => onEvidence(a.evidence_ref)}
              >
                Original tick record <Icon name="arrow" size={12} />
              </button>
              {a.raw_ref && (
                <button
                  className="text-button"
                  onClick={() => onEvidence(a.raw_ref!)}
                >
                  Raw CAS artifact <Icon name="arrow" size={12} />
                </button>
              )}
            </div>
          </details>
        ))}
      </section>
      <section className="integrity-section" aria-label="Full Run integrity">
        <div className="section-heading">
          <div>
            <span className="eyebrow">FULL RUN · PROVENANCE</span>
            <h3>Integrity of the preserved run</h3>
          </div>
          {integrity && (
            <span className="verified-badge">
              <Icon name="check" size={14} />
              Locally verified
            </span>
          )}
        </div>
        <p className="section-intro">
          These checks cover the full archive. They do not describe the
          population or activity at the selected tick.
        </p>
        {error && <p role="alert">{error}</p>}
        {!integrity && !error && <p role="status">Checking provenance…</p>}
        {integrity && (
          <>
            <div className="integrity-checks">
              <div>
                <Icon name="check" />
                <strong>Archive & manifests</strong>
                <span>Pinned SHA-256 matches</span>
              </div>
              <div>
                <Icon name="check" />
                <strong>
                  {integrity.checks.checkpoint_chain} committed boundaries
                </strong>
                <span>Hash chain and event history match</span>
              </div>
              <div>
                <Icon name="check" />
                <strong>{integrity.checks.cas_artifacts} CAS artifacts</strong>
                <span>Content digests verified</span>
              </div>
              <div>
                <Icon name="check" />
                <strong>SQLite integrity: {integrity.checks.sqlite}</strong>
                <span>Materialized state matches</span>
              </div>
            </div>
            <details className="evidence-disclosure">
              <summary>
                Archive identities <span>Locally re-verified</span>
              </summary>
              <HashRow
                label="Archive SHA-256"
                value={integrity.checks.archive_sha256}
              />
              <HashRow
                label="Manifest SHA-256"
                value={integrity.checks.manifest_sha256}
              />
              <HashRow
                label="Grounding manifest SHA-256"
                value={integrity.checks.grounding_manifest_sha256}
              />
              <p className="definition">
                SQLite connection: {integrity.checks.read_only}. Manifest result
                digests are recomputed from canonical JSON.
              </p>
            </details>
            <details className="evidence-disclosure">
              <summary>
                Recorded completion & grounding gates{" "}
                <span>Recorded status · Full Run</span>
              </summary>
              <div className="recorded-status">
                <span>Base status</span>
                <strong>{integrity.recorded.base_status}</strong>
                <span>Grounding status</span>
                <strong>{integrity.recorded.grounding_status}</strong>
              </div>
              <HashRow
                label="Base result digest"
                value={integrity.recorded.base_digest}
              />
              <HashRow
                label="Grounding result digest"
                value={integrity.recorded.grounding_digest}
              />
              <div className="recorded-gates">
                {Object.entries(integrity.recorded.gates).map(([k, v]) => (
                  <span key={k}>
                    {k.split("_")[0]} <strong>{String(v)}</strong>
                  </span>
                ))}
              </div>
              <p className="definition">
                Gate values above were recorded by the completed experiment.
                Local verification checks archived bytes and consistency; it
                does not rerun these scientific gates.
              </p>
              {integrity.manifests.map((m) => (
                <button
                  className="text-button"
                  key={m.ref}
                  onClick={() => onEvidence(m.ref, true)}
                >
                  {m.label} · Full Run <Icon name="arrow" size={12} />
                </button>
              ))}
            </details>
            <details className="evidence-disclosure">
              <summary>
                Final result <span>Full Run · all 20 ticks</span>
              </summary>
              <div className="final-results">
                <span>
                  Founders <strong>{integrity.final_result.founders}</strong>
                </span>
                <span>
                  Final population{" "}
                  <strong>{integrity.final_result.population}</strong>
                </span>
                <span>
                  Births <strong>{integrity.final_result.births}</strong>
                </span>
                <span>
                  Natural deaths{" "}
                  <strong>{integrity.final_result.deaths}</strong>
                </span>
                <span>
                  Generation depth{" "}
                  <strong>{integrity.final_result.generation}</strong>
                </span>
                <span>
                  Birth conflicts{" "}
                  <strong>{integrity.final_result.birth_conflicts}</strong>
                </span>
              </div>
              <table className="scores-table">
                <caption>Selected actions — full run</caption>
                <tbody>
                  {["WAIT", "SEND", "PROPOSE", "ACCEPT", "REJECT"].map(
                    (action) => (
                      <tr key={action}>
                        <th>{action}</th>
                        <td>
                          {integrity.final_result.selected_actions[action] ?? 0}
                        </td>
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
              <p className="outcome-note">
                {integrity.final_result.selected_actions.SEND} SEND selections →{" "}
                {integrity.final_result.messages} committed messages.
                <br />
                {integrity.final_result.selected_actions.ACCEPT} ACCEPT
                selections → {integrity.final_result.births} births.
                <br />
                {integrity.final_result.proposals} proposals created.
              </p>
            </details>
          </>
        )}
      </section>
    </section>
  );
}

export function EvidenceDialog({
  base,
  reference,
  tick,
  fullRun,
  onClose,
}: {
  base: string;
  reference: string;
  tick: number;
  fullRun: boolean;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [data, setData] = useState<RawEvidence | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const el = dialog.current!;
    el.showModal();
    const controller = new AbortController();
    getJSON<RawEvidence>(
      `${base}/evidence/${reference}?tick=${tick}${fullRun ? "&scope=full-run" : ""}`,
      controller.signal,
    )
      .then(setData)
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      });
    return () => {
      controller.abort();
      el.close();
    };
  }, [base, reference, tick, fullRun]);
  return (
    <dialog
      ref={dialog}
      className="evidence-dialog"
      aria-labelledby="evidence-dialog-title"
      onCancel={onClose}
    >
      <div className="dialog-heading">
        <div>
          <span className="eyebrow">
            {fullRun ? "FULL RUN" : `THROUGH TICK ${tick}`} · EXACT SOURCE
          </span>
          <h2 id="evidence-dialog-title">{data?.label ?? "Evidence record"}</h2>
        </div>
        <button
          className="icon-button"
          onClick={onClose}
          aria-label="Close evidence"
        >
          <Icon name="close" />
        </button>
      </div>
      {error && <p role="alert">{error}</p>}
      {!data && !error && <p role="status">Resolving verified evidence…</p>}
      {data && (
        <>
          <div className="raw-metadata">
            <span>
              <Icon name="check" size={15} />
              SHA-256 re-verified on read · {data.byte_length.toLocaleString()}{" "}
              bytes
            </span>
            <CopyButton value={data.content} label="Copy source" />
          </div>
          <code className="raw-digest">{data.ref}</code>
          <p className="definition">
            Original source text, including exact integers. No values have been
            rounded or reformatted.
          </p>
          <pre className="raw-content">{data.content}</pre>
        </>
      )}
    </dialog>
  );
}
