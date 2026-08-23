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
  running: { dot: "●", text: "Running", color: "text-emerald-500" },
  healthy: { dot: "✓", text: "Healthy", color: "text-emerald-500" },
  checking: { dot: "●", text: "Checking...", color: "text-amber-500 animate-pulse" },
  unavailable: { dot: "✗", text: "Unavailable", color: "text-red-500" },
  "not-configured": { dot: "○", text: "Not configured", color: "text-neutral-400" },
};

export default function StatusRow({ label, state }: StatusRowProps) {
  const config = STATE_CONFIG[state];

  return (
    <div className="flex items-center justify-between py-2 border-b border-neutral-800/10 last:border-b-0">
      <span className="text-sm font-medium text-neutral-600 dark:text-neutral-300">
        {label}
      </span>
      <span className={`text-sm font-semibold ${config.color}`}>
        {config.dot} {config.text}
      </span>
    </div>
  );
}
