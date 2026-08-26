"use client";

import { useState } from "react";

import { checkBackendHealth } from "@/lib/api";
import StatusRow, { type StatusState } from "@/components/StatusRow";

/**
 * This is a Client Component ("use client" at the top). It needs to run
 * in the browser because it uses React state (useState) and responds to
 * a button click — things that only exist on the client. Next.js Server
 * Components (the default) render once on the server and can't hold
 * interactive state like this.
 */
export default function SystemStatusCard() {
  const [backendState, setBackendState] = useState<StatusState>("checking");
  const [databaseState, setDatabaseState] = useState<StatusState>("checking");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isChecking, setIsChecking] = useState(false);

  async function handleCheckHealth() {
    setIsChecking(true);
    setBackendState("checking");
    setDatabaseState("checking");
    setErrorMessage(null);

    const result = await checkBackendHealth();

    if (result.ok) {
      setBackendState(result.data.backend === "healthy" ? "healthy" : "unavailable");
      setDatabaseState(result.data.database === "healthy" ? "healthy" : "unavailable");
      if (result.data.database !== "healthy") {
        setErrorMessage("Backend is reachable, but it can't reach the database right now.");
      }
    } else {
      setBackendState("unavailable");
      setDatabaseState("unavailable");
      setErrorMessage("Couldn't reach the backend. Is it running on http://localhost:8000?");
    }

    setIsChecking(false);
  }

  return (
    <div className="repopilot-card">
      <h2 className="card-title">System Status</h2>

      <div>
        <StatusRow label="Frontend" state="running" />
        <StatusRow label="Backend" state={backendState} />
        <StatusRow label="Database" state={databaseState} />
        <StatusRow label="AI" state="not-configured" />
        <StatusRow label="GitHub" state="not-configured" />
      </div>

      {errorMessage && (
        <p className="feedback-error" style={{ marginTop: "12px" }}>
          {errorMessage}
        </p>
      )}

      <button
        id="check-health-btn"
        onClick={handleCheckHealth}
        disabled={isChecking}
        className="status-check-btn"
      >
        {isChecking ? "Checking..." : "Check System Health"}
      </button>
    </div>
  );
}
