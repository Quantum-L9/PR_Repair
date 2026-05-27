# DEFERRED

## Phase 1 intentional deferments

These are intentionally not implemented in Phase 1.

- Connector execution and API transport
- PR ingestion flow
- Finding normalization and dedupe
- Taxonomy classification
- Repair planning
- Git workspace mutation
- Verification execution
- Learning packet generation
- Review comment emission

## Why deferred

Phase 1 is limited to:
- runtime contracts
- repo-context loading
- state persistence
- deterministic phase orchestration primitives
- machine-readable path and tier policy

This keeps the implementation aligned with the approved build order and prevents
premature coupling across later phases.
