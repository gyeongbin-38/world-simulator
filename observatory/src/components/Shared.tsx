import { useState } from "react";
import type { ReactNode } from "react";
import type { Agent } from "../types";

export function Icon({ name, size = 18 }: { name: string; size?: number }) {
  const paths: Record<string, ReactNode> = {
    lock: (
      <>
        <rect x="6" y="10" width="12" height="10" rx="2" />
        <path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v2" />
      </>
    ),
    arrow: <path d="m9 5 7 7-7 7" />,
    back: <path d="m15 5-7 7 7 7" />,
    play: <path d="m8 5 11 7-11 7Z" fill="currentColor" stroke="none" />,
    pause: (
      <>
        <path d="M8 5v14M16 5v14" strokeWidth="3" />
      </>
    ),
    close: <path d="m6 6 12 12M18 6 6 18" />,
    check: <path d="m5 12 4 4L19 6" />,
    copy: (
      <>
        <rect x="8" y="8" width="12" height="12" rx="2" />
        <path d="M15 8V4H4v11h4" />
      </>
    ),
    expand: (
      <>
        <path d="M14 4h6v6M20 4l-7 7M10 20H4v-6m0 6 7-7" />
      </>
    ),
    birth: (
      <>
        <path d="M12 3v18M3 12h18M6 6l12 12M18 6 6 18" />
      </>
    ),
    message: (
      <path d="M20 15a3 3 0 0 1-3 3H9l-5 3V6a3 3 0 0 1 3-3h10a3 3 0 0 1 3 3Z" />
    ),
    proposal: (
      <>
        <circle cx="8" cy="12" r="5" />
        <circle cx="16" cy="12" r="5" />
      </>
    ),
    death: <path d="M5 12h14" />,
    rejection: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="m6 6 12 12" />
      </>
    ),
    action: (
      <>
        <circle cx="12" cy="12" r="8" />
        <path d="M12 7v5l3 2" />
      </>
    ),
    run: (
      <>
        <path d="M5 21V3m0 1h14l-3 5 3 5H5" />
      </>
    ),
    evidence: (
      <>
        <path d="M14 3H5v18h14V8Z M14 3v5h5M8 12h8M8 16h5" />
      </>
    ),
  };
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {paths[name] ?? paths.action}
    </svg>
  );
}

export function OrbitMark() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 40 40"
      width="34"
      height="34"
      fill="none"
    >
      <circle cx="20" cy="20" r="14" stroke="currentColor" strokeWidth="1.4" />
      <ellipse
        cx="20"
        cy="20"
        rx="7"
        ry="14"
        stroke="currentColor"
        strokeWidth="1.2"
        transform="rotate(35 20 20)"
      />
      <circle cx="20" cy="20" r="2.7" fill="currentColor" />
    </svg>
  );
}

export function AgentGlyph({
  agent,
  size = 64,
}: {
  agent: Agent;
  size?: number;
}) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="-40 -40 80 80"
      className={`agent-glyph tone-${agent.slot % 5} ${agent.lifecycle}`}
    >
      <circle className="glyph-fill" r="36" />
      <g
        className="glyph-ink"
        fill="none"
        strokeWidth="1.5"
        transform={`rotate(${agent.slot * 28})`}
      >
        {Array.from({ length: agent.generation ? 6 : 3 }, (_, i) => (
          <ellipse
            key={i}
            rx={agent.generation ? 13 : 11}
            ry="22"
            transform={`rotate(${i * (agent.generation ? 30 : 60)})`}
          />
        ))}
        <circle r="4" />
      </g>
    </svg>
  );
}

export function CopyButton({
  value,
  label = "Copy ID",
}: {
  value: string;
  label?: string;
}) {
  const [message, setMessage] = useState("");
  return (
    <span className="copy-control">
      <button
        className="text-button"
        aria-label={label}
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(value);
            setMessage("Copied");
          } catch {
            setMessage("Select the ID to copy");
          }
        }}
      >
        <Icon name="copy" size={14} />
        <span>{label}</span>
      </button>
      <span role="status">{message}</span>
    </span>
  );
}

export function StatusPanel({
  title,
  children,
  error = false,
}: {
  title: string;
  children: ReactNode;
  error?: boolean;
}) {
  return (
    <section
      className={`status-panel ${error ? "is-error" : ""}`}
      role={error ? "alert" : "status"}
    >
      <OrbitMark />
      <h1>{title}</h1>
      <p>{children}</p>
    </section>
  );
}

export function HashRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="hash-row">
      <span>{label}</span>
      <code>{value}</code>
      <CopyButton value={value} label={`Copy ${label}`} />
    </div>
  );
}
