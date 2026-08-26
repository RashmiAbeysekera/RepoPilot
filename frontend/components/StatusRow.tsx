export type StatusState =
  | "running"
  | "healthy"
  | "checking"
  | "unavailable"
  | "not-configured";

interface StatusRowProps {
  label: string;
  state: StatusState;
}

/**
 * Visual + text configuration for each possible status state.
 * Kept as a lookup table (rather than a chain of if/else) so adding a
 * new state later is a one-line change.
 */
const STATE_CONFIG: Record<StatusState, { dot: string; text: string; color: string }> = {
  running:          { dot: "●", text: "Running",       color: "#22c55e" },
  healthy:          { dot: "✓", text: "Healthy",       color: "#22c55e" },
  checking:         { dot: "●", text: "Checking...",   color: "#f59e0b" },
  unavailable:      { dot: "✗", text: "Unavailable",   color: "#ef4444" },
  "not-configured": { dot: "○", text: "Not configured", color: "#5c6080" },
};

export default function StatusRow({ label, state }: StatusRowProps) {
  const config = STATE_CONFIG[state];
  const isChecking = state === "checking";

  return (
    <div className="status-row">
      <span style={{ fontSize: "0.875rem", fontWeight: 500, color: "#9098b8" }}>
        {label}
      </span>
      <span
        style={{
          fontSize: "0.875rem",
          fontWeight: 600,
          color: config.color,
          animation: isChecking ? "pulse 1.5s ease-in-out infinite" : "none",
        }}
      >
        {config.dot} {config.text}
      </span>
    </div>
  );
}
