export type View = "Overview" | "World" | "Lineage" | "Timeline" | "Evidence";
export interface Run {
  id: string;
  name: string;
  horizon: number;
  founders: number;
  observation: string;
  integrity: string;
}
export interface Agent {
  id: string;
  alias: string;
  slot: number;
  generation: number;
  lifecycle: "born" | "active" | "dead";
  birth_tick: number;
  first_active_tick: number;
  death_tick: number | null;
  death_commit_tick: number | null;
  age: number;
  parents: string[];
  children: string[];
  has_cognition: boolean;
}
export interface Attempt {
  id: string;
  tick: number;
  agent_id: string;
  selected_action: string;
  law_admitted: boolean;
  target_id: string | null;
  evidence_ref: string;
  raw_ref: string | null;
  gateway_intent: { kind: string; payload: Record<string, unknown> } | null;
  proposal_grounding: {
    handle_map: { handle: string; canonical_proposal_id: string }[];
    raw_handle_candidate: unknown;
    mapped_canonical_candidate: unknown;
  } | null;
  probabilities: Record<string, number>;
  score_vector: Record<string, number>;
  parse_status: string;
}
export interface Event {
  id: string;
  tick: number;
  category: string;
  title: string;
  detail: string;
  agent_ids: string[];
  canonical: boolean;
  evidence_ref: string;
  record: Record<string, unknown>;
}
export interface Message {
  message_id: string;
  sender_id: string;
  recipient_id: string;
  body: string;
  committed_tick: number;
  available_tick: number;
}
export interface Proposal {
  proposal_id: string;
  proposer_id: string;
  target_id: string;
  created_tick: number;
  state: string;
}
export interface Birth {
  child_id: string;
  parent_ids: string[];
  birth_tick: number;
  first_active_tick: number;
  proposal_id: string;
}
export interface Frame {
  run_id: string;
  tick: number;
  boundary_tick: number;
  state_version: number;
  state_hash: string;
  status: string;
  mode: string;
  metrics: {
    population: number;
    generation: number;
    births: number;
    deaths: number;
    messages: number;
    proposals: number;
  };
  agents: Agent[];
  attempts: Attempt[];
  events: Event[];
  messages: Message[];
  proposals: Proposal[];
  lineage: Birth[];
  evidence_ref: string | null;
  projection_schema: string;
}
export interface Integrity {
  scope: string;
  run_id: string;
  local_status: string;
  checks: {
    archive_sha256: string;
    manifest_sha256: string;
    grounding_manifest_sha256: string;
    sqlite: string;
    checkpoint_chain: number;
    cas_artifacts: number;
    materialized_state: string;
    tick_records: string;
    manifest_digests: string;
    read_only: string;
  };
  recorded: {
    base_status: string;
    base_digest: string;
    grounding_status: string;
    grounding_digest: string;
    gates: Record<string, boolean>;
    replay: Record<string, unknown>;
    code_commit: string;
  };
  final_result: Frame["metrics"] & {
    founders: number;
    selected_actions: Record<string, number>;
    birth_conflicts: number;
  };
  manifests: { ref: string; label: string }[];
}
export interface RawEvidence {
  ref: string;
  label: string;
  scope: string;
  verified: boolean;
  byte_length: number;
  content: string;
}
export const lifeLabel = (a: Agent) =>
  a.lifecycle === "born"
    ? "Born · not active"
    : a.lifecycle === "dead"
      ? "Dead"
      : "Active / alive";
export const shortId = (id: string) =>
  id.length > 26 ? `${id.slice(0, 8)}…${id.slice(-6)}` : id;
export const aliasFor = (frame: Frame, id: string) =>
  frame.agents.find((a) => a.id === id)?.alias ?? shortId(id);

export async function getJSON<T>(
  url: string,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(url, { method: "GET", signal });
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      data.detail
        ? `${data.error}: ${data.detail}`
        : (data.error ?? `Request failed (${response.status})`),
    );
  return data as T;
}
