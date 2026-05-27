# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [learning]
# tags: [patterns, failures, governance]
# owner: platform
# status: active
# --- /L9_META ---

from __future__ import annotations

from collections import Counter, defaultdict

from pr_repair.types import LearningPacket, RepairExecution


def extract_learning_packets(executions: list[RepairExecution]) -> list[LearningPacket]:
    """
    Extract recurring failure patterns from completed repair executions.

    Rules:
    - only completed or rollback/failure outcomes contribute evidence
    - repeated failures are grouped by simple stable keys
    - output remains recommendation-only; no repo files are mutated
    """
    grouped_by_pr: dict[int, list[RepairExecution]] = defaultdict(list)
    for execution in executions:
        grouped_by_pr[execution.pr_ref.pr_number].append(execution)

    packets: list[LearningPacket] = []
    for pr_number, items in sorted(grouped_by_pr.items()):
        repeated_failures = _collect_failure_patterns(items)
        agent_recommendations = _build_agent_recommendation_lines(repeated_failures)
        validator_recommendations = _build_validator_recommendation_lines(repeated_failures)
        evidence_refs = [execution.plan_id for execution in items]
        confidence = _compute_confidence(items, repeated_failures)

        packets.append(
            LearningPacket(
                packet_id=f"learning-pr-{pr_number}",
                source_prs=[pr_number],
                repeated_failures=repeated_failures,
                agent_md_recommendations=agent_recommendations,
                validator_recommendations=validator_recommendations,
                evidence_refs=evidence_refs,
                confidence=confidence,
            )
        )
    return packets


def _collect_failure_patterns(executions: list[RepairExecution]) -> list[str]:
    counter: Counter[str] = Counter()
    for execution in executions:
        counter[execution.status] += 1
        verification = execution.verification_result
        if verification is not None and not verification.success:
            counter[f"verification_exit_{verification.exit_code}"] += 1
            if "agent-check" in " ".join(verification.command):
                counter["verification_make_agent_check_failure"] += 1
    ordered = [key for key, _value in counter.most_common() if key != "completed"]
    return ordered


def _build_agent_recommendation_lines(repeated_failures: list[str]) -> list[str]:
    recommendations: list[str] = []
    for pattern in repeated_failures:
        if pattern == "approval_required":
            recommendations.append(
                "Add stronger preflight instructions to avoid generating T3/T4/T5 repair attempts without explicit approval."
            )
        elif pattern == "rolled_back_verification_failed":
            recommendations.append(
                "Strengthen fix prompts to require `make agent-check` parity before proposing repo changes."
            )
        elif pattern == "verification_make_agent_check_failure":
            recommendations.append(
                "Add an explicit agent rule: repairs must satisfy all seven `make agent-check` gates before they are considered valid."
            )
        elif pattern.startswith("verification_exit_"):
            recommendations.append(
                f"Record troubleshooting guidance for `{pattern}` in AGENT.md pre-commit remediation guidance."
            )
    return list(dict.fromkeys(recommendations))


def _build_validator_recommendation_lines(repeated_failures: list[str]) -> list[str]:
    recommendations: list[str] = []
    for pattern in repeated_failures:
        if pattern == "approval_required":
            recommendations.append(
                "Add a validator rule that blocks execution plans exceeding configured write ceiling or touching protected paths."
            )
        elif pattern == "rolled_back_verification_failed":
            recommendations.append(
                "Add a validator rule that detects non-verifiable patch plans before file mutation."
            )
        elif pattern == "verification_make_agent_check_failure":
            recommendations.append(
                "Add a validator check ensuring plan outputs map directly to repo verification contract `make agent-check`."
            )
        elif pattern.startswith("verification_exit_"):
            recommendations.append(
                f"Track `{pattern}` as a validator telemetry bucket for recurring repair failure analysis."
            )
    return list(dict.fromkeys(recommendations))


def _compute_confidence(executions: list[RepairExecution], repeated_failures: list[str]) -> float:
    if not executions:
        return 0.0
    if not repeated_failures:
        return 0.25
    return min(1.0, 0.5 + (0.1 * len(repeated_failures)))
