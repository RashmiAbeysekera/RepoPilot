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
      // User-facing message stays generic; the real cause (network,
      // timeout, unexpected shape) is already logged to the console
      // for debugging — see lib/api.ts.
      setErrorMessage("Couldn't reach the backend. Is it running on http://localhost:8000?");
    }

    setIsChecking(false);
  }

  return (
    <div className="w-full max-w-md rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-6 shadow-sm">
      <h2 className="text-lg font-semibold mb-4">System Status</h2>

      <div className="flex flex-col">
        <StatusRow label="Frontend" state="running" />
        <StatusRow label="Backend" state={backendState} />
        <StatusRow label="Database" state={databaseState} />
        <StatusRow label="AI" state="not-configured" />
        <StatusRow label="GitHub" state="not-configured" />
      </div>

      {errorMessage && (
        <p className="mt-4 text-sm text-red-500">{errorMessage}</p>
      )}

      <button
        onClick={handleCheckHealth}
        disabled={isChecking}
        className="mt-5 w-full rounded-lg bg-neutral-900 dark:bg-white text-white dark:text-neutral-900 font-medium py-2 text-sm hover:opacity-90 disabled:opacity-50 transition-opacity"
      >
        {isChecking ? "Checking..." : "Check System Health"}
      </button>
    </div>
  );
}
