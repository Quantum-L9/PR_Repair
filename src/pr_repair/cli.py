# --- L9_META ---
# l9_schema: 1
# origin: pr_repair_pipeline
# engine: pr_repair
# layer: [entrypoint]
# tags: [cli, dispatch]
# owner: platform
# status: active
# --- /L9_META ---

from __future__ import annotations

import argparse
from pathlib import Path

from pr_repair.config import load_config, resolve_verify_command
from pr_repair.pipeline.run_pipeline import run_pipeline
from pr_repair.state_store import StateStore
from pr_repair.types import ExecutionMode
from pr_repair.verification.native_runner import run_verification
from pr_repair.verification.report_builder import build_verification_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pr-repair")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument(
        "--mode",
        choices=[mode.value for mode in ExecutionMode],
        default=None,
    )
    run_parser.add_argument(
        "--payload-path",
        default=None,
        help="Path to agent_review_payload.json (default: artifacts/agent_review_payload.json).",
    )

    subparsers.add_parser("verify")
    subparsers.add_parser("learn")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    config = load_config()

    if args.command == "run":
        updates: dict[str, object] = {}
        if args.mode is not None:
            updates["mode"] = ExecutionMode(args.mode)
        if args.payload_path is not None:
            updates["payload_path"] = Path(args.payload_path)
        if updates:
            config = config.model_copy(update=updates)
        return run_pipeline(config)

    if args.command == "verify":
        report = run_verification(resolve_verify_command(config))
        store = StateStore(config.output_dir)
        store.write_markdown("verification_report.md", build_verification_markdown(report))
        return 0 if report.success else report.exit_code

    if args.command == "learn":
        config = config.model_copy(update={"mode": ExecutionMode.learn_only})
        return run_pipeline(config)

    msg = f"Unsupported command: {args.command}"
    raise ValueError(msg)
