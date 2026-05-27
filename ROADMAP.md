# Roadmap

## MVP

- Preserve local-first dry-run and repair-verify flows.
- Preserve GitHub, CodeRabbit, and Codecov signal intake.
- Preserve normalization, deduplication, clustering, candidate generation, classification, planning, approval, patching, verification, rollback, learning, and artifacts.
- Preserve existing test suite.

## Enterprise hardening

- Expand policy configuration coverage.
- Add stricter artifact schema checks.
- Add repository-specific governance profiles.
- Add richer approval routing without changing local-first behavior.

## Hosted orchestration path

- Treat hosted execution as an orchestration wrapper around the canonical local runtime.
- Keep connector, governance, verification, and rollback boundaries intact.

## Compliance-readiness path

- Formalize artifact retention.
- Add traceability matrix output.
- Add policy evidence bundles.
- Add audit-mode validation reports.
