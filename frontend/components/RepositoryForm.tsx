"use client";

import { useState } from "react";
import { addRepository } from "@/lib/api";

interface RepositoryFormProps {
  /** Called with the newly created repository after a successful add. */
  onRepositoryAdded: () => void;
}

/**
 * Form for adding a new GitHub repository.
 *
 * The user enters a GitHub URL and clicks "Add Repository".
 * We send a POST request to the FastAPI backend, which validates
 * the URL, saves it to PostgreSQL, and returns the saved record.
 *
 * Error states are surfaced directly in the form — no page reload.
 */
export default function RepositoryForm({ onRepositoryAdded }: RepositoryFormProps) {
  const [url, setUrl] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault(); // prevent browser page reload on form submit
    setError(null);
    setSuccessMessage(null);

    const trimmedUrl = url.trim();
    if (!trimmedUrl) {
      setError("Please enter a GitHub repository URL.");
      return;
    }

    setIsSubmitting(true);
    const result = await addRepository(trimmedUrl);
    setIsSubmitting(false);

    if (result.ok) {
      setSuccessMessage(`Added ${result.data.full_name}`);
      setUrl(""); // clear the input for the next entry
      onRepositoryAdded(); // tell the parent to refresh the list
    } else {
      setError(result.error);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="repopilot-card">
      <h2 className="card-title">Add Repository</h2>

      <div className="form-group">
        <label htmlFor="repo-url-input" className="form-label">
          GitHub Repository URL
        </label>
        <input
          id="repo-url-input"
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://github.com/owner/repository"
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
        id="add-repository-btn"
        type="submit"
        disabled={isSubmitting}
        className="btn-primary"
      >
        {isSubmitting ? "Adding..." : "Add Repository"}
      </button>
    </form>
  );
}
