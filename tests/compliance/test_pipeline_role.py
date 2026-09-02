"""v0.1 boundary: this repository is a standalone PR assistant.

`l9-ci-debt-resolver` defines a bounded delegation protocol in which a delegate
may propose and never conclude. This repository does not implement it, and runs
a complete parallel repair loop instead. Two systems each built as the
organisation's repair owner is duplicate authority by design intent; v0.1
resolves it by scope, and these tests keep the declaration honest.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
GOVERNANCE = ROOT / "GOVERNANCE.md"
WORKFLOW = ROOT / ".github" / "workflows" / "pr-repair.yml"

# The resolver's delegation contracts. Implementing either is a deliberate
# architectural decision that must also flip the declaration below.
DELEGATION_CONTRACTS = ("l9.pr-repair-request/v1", "l9.pr-repair-proposal/v1")


def _declared_role() -> dict[str, object]:
    block = re.search(r"```yaml\n(.*?)```", GOVERNANCE.read_text(encoding="utf-8"), re.DOTALL)
    assert block is not None, "GOVERNANCE.md must declare the pipeline role in a yaml block"
    parsed = yaml.safe_load(block.group(1))
    assert isinstance(parsed, dict)
    return parsed


def test_repository_declares_itself_a_standalone_pr_assistant() -> None:
    assert _declared_role() == {
        "pipeline_role": "standalone_pr_assistant",
        "debt_pipeline_authority": False,
        "remote_mutation_default": False,
        "verification_authority": "local_only",
        "resolver_delegation_implemented": False,
    }


@pytest.mark.parametrize("contract", DELEGATION_CONTRACTS)
def test_delegation_declaration_matches_the_source(contract: str) -> None:
    """The declaration must track the code, not drift from it.

    If someone implements the resolver's protocol, this fails and forces
    `resolver_delegation_implemented` to be updated in the same change --
    rather than leaving the repository silently claiming to be standalone while
    acting as a delegate.
    """
    implemented = _declared_role()["resolver_delegation_implemented"] is True
    present = any(
        contract in path.read_text(encoding="utf-8", errors="ignore")
        for path in (ROOT / "src").rglob("*.py")
    )
    assert present == implemented, (
        f"{contract} presence in src/ ({present}) contradicts "
        f"resolver_delegation_implemented ({implemented})"
    )


def test_workflow_keeps_remote_mutation_off_by_default() -> None:
    """`remote_mutation_default: false` must describe the shipped workflow.

    This repository's library can push. The deployment deliberately cannot:
    push is hardcoded off, and enabling it is a reviewed workflow edit rather
    than a configuration convenience.
    """
    assert _declared_role()["remote_mutation_default"] is False
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "PR_FIX_ALLOW_PUSH: '0'" in workflow
    assert "vars.PR_REPAIR_ENABLED == 'true'" in workflow
    assert "vars.PR_REPAIR_MODE || 'dry_run'" in workflow
