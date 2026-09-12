"use client";

import { useEffect, useState } from "react";

import { checkBackendHealth, API_BASE_URL } from "@/lib/api";
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
  const [aiState, setAiState] = useState<StatusState>("checking");
  const [githubState, setGithubState] = useState<StatusState>("checking");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isChecking, setIsChecking] = useState(false);

  const applyHealthResult = (result: Awaited<ReturnType<typeof checkBackendHealth>>) => {
    if (result.ok) {
      setBackendState(result.data.backend === "healthy" ? "healthy" : "unavailable");
      setDatabaseState(result.data.database === "healthy" ? "healthy" : "unavailable");

      const aiStatus = result.data.ai;
      setAiState(aiStatus === "healthy" ? "healthy" : aiStatus === "unavailable" ? "unavailable" : "not-configured");

      const ghStatus = result.data.github;
      setGithubState(ghStatus === "healthy" ? "healthy" : ghStatus === "unavailable" ? "unavailable" : "not-configured");

      if (result.data.database !== "healthy") {
        setErrorMessage("Backend is reachable, but it can't reach the database right now.");
      }
    } else {
      setBackendState("unavailable");
      setDatabaseState("unavailable");
      setAiState("unavailable");
      setGithubState("unavailable");
      setErrorMessage(`Couldn't reach the backend at ${API_BASE_URL}. If hosted on a free-tier platform (such as Render), it may take 30–60 seconds to wake up from sleep.`);
    }
  };

  async function handleCheckHealth() {
    setIsChecking(true);
    setBackendState("checking");
    setDatabaseState("checking");
    setAiState("checking");
    setGithubState("checking");
    setErrorMessage(null);

    const result = await checkBackendHealth();
    applyHealthResult(result);
    setIsChecking(false);
  }

  useEffect(() => {
    let ignore = false;
    checkBackendHealth().then((result) => {
      if (!ignore) {
        applyHealthResult(result);
      }
    });
    return () => {
      ignore = true;
    };
  }, []);

  return (
    <div className="repopilot-card">
      <h2 className="card-title">System Status</h2>

      <div>
        <StatusRow label="Frontend" state="running" />
        <StatusRow label="Backend" state={backendState} />
        <StatusRow label="Database" state={databaseState} />
        <StatusRow label="AI" state={aiState} />
        <StatusRow label="GitHub" state={githubState} />
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
