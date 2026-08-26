"use client";

import { useState } from "react";
import { importRepository } from "@/lib/api";

interface RepositoryFormProps {
  /** Called with the newly created repository after a successful import. */
  onRepositoryAdded: () => void;
}

/**
 * Form for importing a public GitHub repository.
 *
 * The user enters a GitHub URL and clicks "Import Repository".
 * We send a POST request to /api/repositories/import, which fetches metadata
 * via GitHub REST API, saves it to PostgreSQL, and returns the saved record.
 */
export default function RepositoryForm({ onRepositoryAdded }: RepositoryFormProps) {
  const [url, setUrl] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setSuccessMessage(null);

    const trimmedUrl = url.trim();
    if (!trimmedUrl) {
      setError("Please enter a public GitHub repository URL.");
      return;
    }

    setIsSubmitting(true);
    const result = await importRepository(trimmedUrl);
    setIsSubmitting(false);

    if (result.ok) {
      setSuccessMessage(`Successfully imported ${result.data.full_name}`);
      setUrl("");
      onRepositoryAdded();
    } else {
      setError(result.error);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="repopilot-card">
      <h2 className="card-title">Import GitHub Repository</h2>

      <div className="form-group">
        <label htmlFor="repo-url-input" className="form-label">
          Public GitHub Repository URL
        </label>
        <input
          id="repo-url-input"
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://github.com/facebook/react"
          disabled={isSubmitting}
          className="form-input"
          aria-describedby={error ? "repo-url-error" : undefined}
        />
      </div>

      {error && (
        <p id="repo-url-error" className="feedback-error" role="alert">
          {error}
        </p>
      )}

      {successMessage && (
        <p className="feedback-success" role="status">
          ✓ {successMessage}
        </p>
      )}

      <button
        id="import-repository-btn"
        type="submit"
        disabled={isSubmitting}
        className="btn-primary"
      >
        {isSubmitting ? "Importing..." : "Import Repository"}
      </button>
    </form>
  );
}

