"use client";

import { useState } from "react";
import SystemStatusCard from "@/components/SystemStatusCard";
import RepositoryForm from "@/components/RepositoryForm";
import RepositoryList from "@/components/RepositoryList";

/**
 * Root page — holds the system health check and repository management UI.
 *
 * We use "use client" here because we need state (refreshTrigger) to
 * coordinate the form and list. The page itself is simple: it wires
 * the two components together and provides the refresh signal.
 *
 * refreshTrigger: a counter that increments each time a repository is
 * added. RepositoryList watches this value and reloads when it changes.
 * This is a simple, explicit way to coordinate parent → child updates
 * without needing a global state library.
 */
export default function Home() {
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  function handleRepositoryAdded() {
    setRefreshTrigger((prev) => prev + 1);
  }

  return (
    <main className="page-container">
      <header className="page-header">
        <h1 className="page-title">RepoPilot</h1>
        <p className="page-subtitle">AI-powered software engineering assistant</p>
      </header>

      <div className="content-grid">
        {/* System health — shows backend and database status */}
        <section aria-label="System status">
          <SystemStatusCard />
        </section>

        {/* Repository management */}
        <section aria-label="Repository management" className="repo-section">
          <RepositoryForm onRepositoryAdded={handleRepositoryAdded} />
          <RepositoryList refreshTrigger={refreshTrigger} />
        </section>
      </div>
    </main>
  );
}
