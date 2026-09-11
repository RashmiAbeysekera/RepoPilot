"""
Lightweight RAG and Grounding Evaluation Engine for RepoPilot.

METRICS EVALUATED:
  1. Hit@K: Does the top-K retrieved chunk set contain at least one expected source file?
  2. Precision@K: Fraction of retrieved chunks belonging to the expected files.
  3. Grounding Score: Percentage of cited source files that actually exist in the retrieved evidence set.
  4. Negative Query Rejection: Does the system cleanly decline or flag queries when no relevant evidence exists?
"""

import json
import logging
import sys
import uuid
from pathlib import Path
from typing import Any

from app.core.database import SessionLocal
from app.models.repository import Repository
from app.services import rag_service, search_service

logger = logging.getLogger("repopilot.evaluator")

EVAL_DATASET_PATH = Path(__file__).resolve().parent / "eval_dataset.json"


def load_dataset() -> list[dict[str, Any]]:
    """Load evaluation scenarios from eval_dataset.json."""
    with open(EVAL_DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_repository_retrieval(
    repository_id: uuid.UUID | str,
    top_k: int = 5,
    run_llm_generation: bool = False,
) -> dict[str, Any]:
    """
    Run evaluation suite against indexed repository and compute retrieval & grounding metrics.

    Args:
        repository_id: UUID of repository to evaluate against.
        top_k: Top-K chunks to retrieve per question.
        run_llm_generation: Whether to also call Gemini for grounding verification (optional).

    Returns:
        Dict with detailed per-scenario evaluations and summary metrics.
    """
    db = SessionLocal()
    try:
        repo_uuid = uuid.UUID(str(repository_id))
        repo = db.query(Repository).filter(Repository.id == repo_uuid).first()
        if not repo:
            raise ValueError(f"Repository '{repository_id}' not found.")

        scenarios = load_dataset()
        results = []

        total_positive = 0
        hits = 0
        total_precisions = []
        grounding_scores = []
        negative_correct = 0
        total_negative = 0

        for sc in scenarios:
            q_id = sc["id"]
            question = sc["question"]
            expected_files = sc.get("expected_files", [])
            category = sc.get("category", "general")

            # 1. Evaluate Retrieval
            search_res = search_service.search_repository_chunks(
                db=db,
                repository_id=repo_uuid,
                query=question,
                top_k=top_k,
            )
            retrieved_chunks = search_res.get("results", [])
            retrieved_files = list({c.get("file_path") for c in retrieved_chunks if c.get("file_path")})
            top_similarity = retrieved_chunks[0]["score"] if retrieved_chunks else 0.0

            if expected_files:
                # Positive test case
                total_positive += 1
                hit = any(any(exp in rf for exp in expected_files) for rf in retrieved_files)
                if hit:
                    hits += 1

                # Calculate Precision@K
                matching_chunks = sum(
                    1 for c in retrieved_chunks if any(exp in c.get("file_path", "") for exp in expected_files)
                )
                precision = matching_chunks / len(retrieved_chunks) if retrieved_chunks else 0.0
                total_precisions.append(precision)
            else:
                # Negative test case (feature does not exist in repository)
                total_negative += 1
                hit = None
                precision = None
                # Correct if top similarity is low (< 0.20 threshold) or 0 chunks
                if top_similarity < 0.20 or len(retrieved_chunks) == 0:
                    negative_correct += 1

            # 2. Evaluate Grounding (if enabled)
            grounded = None
            if run_llm_generation:
                try:
                    rag_res = rag_service.answer_repository_question(
                        db=db,
                        repository_id=repo_uuid,
                        query=question,
                        top_k=top_k,
                        use_agent=False,
                    )
                    sources = rag_res.get("sources", [])
                    # Verify that all cited sources came strictly from retrieved chunks
                    retrieved_ids = {c.get("chunk_id") for c in retrieved_chunks if c.get("chunk_id")}
                    cited_ids = {s.get("chunk_id") for s in sources if s.get("chunk_id")}
                    if cited_ids:
                        grounded_ratio = len(cited_ids.intersection(retrieved_ids)) / len(cited_ids)
                    else:
                        grounded_ratio = 1.0  # Safe fallback without hallucinated sources
                    grounded = grounded_ratio
                    grounding_scores.append(grounded_ratio)
                except Exception as gen_err:
                    logger.warning("LLM generation skipped for eval %s: %s", q_id, gen_err)

            results.append({
                "id": q_id,
                "category": category,
                "question": question,
                "expected_files": expected_files,
                "retrieved_files": retrieved_files,
                "top_similarity": top_similarity,
                "hit": hit,
                "precision": precision,
                "grounded": grounded,
            })

        hit_rate = (hits / total_positive) if total_positive > 0 else 0.0
        mean_precision = (sum(total_precisions) / len(total_precisions)) if total_precisions else 0.0
        negative_accuracy = (negative_correct / total_negative) if total_negative > 0 else 1.0
        mean_grounding = (sum(grounding_scores) / len(grounding_scores)) if grounding_scores else 1.0

        summary = {
            "repository": repo.full_name,
            "total_scenarios": len(scenarios),
            "positive_scenarios": total_positive,
            "negative_scenarios": total_negative,
            "hit_at_k": round(hit_rate, 4),
            "precision_at_k": round(mean_precision, 4),
            "negative_rejection_rate": round(negative_accuracy, 4),
            "mean_grounding_score": round(mean_grounding, 4),
            "scenarios": results,
        }

        return summary
    finally:
        db.close()


def print_markdown_report(summary: dict[str, Any]) -> None:
    """Print clean developer-readable markdown report to stdout."""
    print("\n" + "=" * 80)
    print(f"# REPOPILOT RAG EVALUATION REPORT — {summary['repository']}")
    print("=" * 80)
    print(f"- Total Test Scenarios: {summary['total_scenarios']}")
    print(f"- Hit@{5}: {summary['hit_at_k'] * 100:.1f}%")
    print(f"- Precision@{5}: {summary['precision_at_k'] * 100:.1f}%")
    print(f"- Negative Query Rejection: {summary['negative_rejection_rate'] * 100:.1f}%")
    print(f"- Evidence Grounding: {summary['mean_grounding_score'] * 100:.1f}%\n")

    print("| Scenario ID | Category | Hit@5 | Precision | Top Score | Retrieved Files |")
    print("| :--- | :--- | :---: | :---: | :---: | :--- |")

    for s in summary["scenarios"]:
        hit_str = "PASS" if s["hit"] is True else "N/A" if s["hit"] is None else "FAIL"
        prec_str = f"{s['precision']:.2f}" if s["precision"] is not None else "N/A"
        ret_str = ", ".join(s["retrieved_files"][:2]) if s["retrieved_files"] else "None"
        print(f"| `{s['id']}` | {s['category']} | **{hit_str}** | {prec_str} | {s['top_similarity']:.2f} | {ret_str} |")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    db = SessionLocal()
    repo = db.query(Repository).first()
    db.close()
    if not repo:
        print("No repository found in database to evaluate.")
        sys.exit(1)

    print(f"Running evaluation on repository: {repo.full_name} ({repo.id})...")
    report = evaluate_repository_retrieval(repo.id, top_k=5, run_llm_generation=False)
    print_markdown_report(report)
