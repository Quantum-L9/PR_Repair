# Recursive Original-Pack Audit

## Scope

Audited `/mnt/data/PR Agent.zip` recursively, including all nested PR repair zip bundles. Compared the fully expanded original pack against the consolidated clean pack.

## Original Pack Inventory

- Top-level original files after initial unzip: 30
- Nested zip bundles extracted: 14
- Fully recursive file count, including nested bundle contents: 356
- Relevant non-zip/non-cache files reviewed: 246

## Clean Pack Inventory After Audit

- Canonical repo: `pr_repair`
- Bundle recursion: removed
- Phase zip copies: removed
- macOS metadata: removed
- Python cache files: removed in v2
- Tests preserved and expanded

## Findings

### Preserved correctly

- `src/pr_repair/ingestion/*`
- `src/pr_repair/normalization/*`
- `src/pr_repair/classification/*`
- `src/pr_repair/connectors/*`
- `src/pr_repair/planning/*`
- `src/pr_repair/repair/*`
- `src/pr_repair/patching/*`
- `src/pr_repair/verification/*`
- `src/pr_repair/learning/*`
- `src/pr_repair/runtime/*`
- `src/pr_repair/artifacts/*`
- `src/pr_repair/output/*`
- `src/pr_repair/repo_context/*`
- Runtime models in `types.py`
- State persistence in `state_store.py`
- Governance and protected-path behavior
- CLI and pyproject packaging
- Unit, integration, and security tests

### Missed in v1, restored in v2

- `src/pr_repair/clustering.py`
- `src/pr_repair/candidates.py`
- `FindingCluster` model
- `RepairCandidate` model
- `tests/unit/test_clustering.py`
- `tests/unit/test_candidates.py`
- `docs/archive/make_pr_pipeline_v2_1.plan.md`

### Deliberately excluded

- Nested zip bundles
- `__MACOSX` files
- generated full-content dumps
- duplicate phase-level `pyproject.toml` files
- duplicate phase-level README variants
- stale canonical copies
- Python bytecode/cache artifacts

## Judgment

The v1 pack preserved the main executable PR repair pipeline, including ingestion and normalization. The recursive audit found one meaningful older subsystem that should have been carried forward: clustering and candidate generation. v2 restores it without adding stubs or fake behavior.
