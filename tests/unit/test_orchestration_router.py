from pr_repair.orchestration.router import RouteResult, route_findings
from pr_repair.types import Finding, ReviewDisposition, Severity, SourceName


def _finding(finding_id: str, disposition: ReviewDisposition) -> Finding:
    return Finding(
        finding_id=finding_id,
        pr_number=1,
        source_name=SourceName.agent_review,
        source_priority=110,
        severity=Severity.medium,
        category="lint_failure",
        message="msg",
        file_path="a.py",
        line_start=1,
        line_end=1,
        replacement_text="x" if disposition is ReviewDisposition.autofix else None,
        review_disposition=disposition,
        repairable=disposition is ReviewDisposition.autofix,
        fingerprint=f"fp-{finding_id}",
    )


def test_route_splits_by_disposition() -> None:
    findings = [
        _finding("af-1", ReviewDisposition.autofix),
        _finding("mr-1", ReviewDisposition.manual_review),
        _finding("af-2", ReviewDisposition.autofix),
    ]

    route = route_findings(findings)

    assert isinstance(route, RouteResult)
    assert [f.finding_id for f in route.autofix] == ["af-1", "af-2"]
    assert [f.finding_id for f in route.manual] == ["mr-1"]
    assert route.total == 3


def test_route_handles_missing_disposition_as_manual() -> None:
    f = _finding("x", ReviewDisposition.manual_review).model_copy(
        update={"review_disposition": None}
    )

    route = route_findings([f])

    assert route.autofix == []
    assert [x.finding_id for x in route.manual] == ["x"]


def test_route_empty() -> None:
    route = route_findings([])
    assert route.autofix == []
    assert route.manual == []
    assert route.total == 0
