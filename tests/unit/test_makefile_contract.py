from pathlib import Path


def test_makefile_targets_match_cli_contract() -> None:
    makefile = Path("Makefile").read_text(encoding="utf-8")

    assert "pr-fix:" in makefile
    assert "python -m pr_repair.cli run --mode repair_and_verify" in makefile

    assert "pr-fix-dry:" in makefile
    assert "python -m pr_repair.cli run --mode dry_run" in makefile

    assert "pr-fix-propose:" in makefile
    assert "python -m pr_repair.cli run --mode propose_only" in makefile

    assert "pr-fix-verify:" in makefile
    assert "python -m pr_repair.cli verify" in makefile

    assert "pr-fix-learn:" in makefile
    assert "python -m pr_repair.cli learn" in makefile
