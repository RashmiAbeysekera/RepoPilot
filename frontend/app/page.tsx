"use client";

import { useState } from "react";
import SystemStatusCard from "@/components/SystemStatusCard";
import RepositoryForm from "@/components/RepositoryForm";
import RepositoryList from "@/components/RepositoryList";

/**
 * Root page — holds system health check, repository import, and repository management UI.
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

      <div className="dashboard-container">
        {/* Top Control Panel Grid — Health & Import side-by-side */}
        <section aria-label="System control panel" className="top-control-grid">
          <SystemStatusCard />
          <RepositoryForm onRepositoryAdded={handleRepositoryAdded} />
        </section>

        {/* Main Repository Explorer Workspace — Full width */}
        <section aria-label="Repository management" className="main-workspace-section">
          <RepositoryList refreshTrigger={refreshTrigger} />
        </section>
      </div>
    </main>
  );
}
