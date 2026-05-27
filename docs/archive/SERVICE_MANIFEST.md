# Service Manifest

## Service
- name: pr_repair
- type: local-first microservice
- domain: PR signal interpretation, safe repair planning, deterministic repair execution
- L9 fit: repo-adjacent node/service for governance-aware remediation and learning

## Public modules
- `pr_repair.cli`
- `pr_repair.config`
- `pr_repair.types`
- `pr_repair.connectors`
- `pr_repair.ingestion`
- `pr_repair.normalization`
- `pr_repair.classification`
- `pr_repair.planning`
- `pr_repair.workspace`
- `pr_repair.repair`
- `pr_repair.verification`
- `pr_repair.output`
- `pr_repair.learning`
- `pr_repair.pipeline`

## Critical public functions
- `load_config`
- `collect_candidate_prs`
- `ingest_tool_findings`
- `ingest_comment_findings`
- `normalize_bundle`
- `dedupe_findings`
- `classify_findings`
- `build_repair_plan`
- `requires_human_approval`
- `generate_patch_instructions`
- `apply_patch_instructions`
- `execute_repair_plan`
- `run_verification`
- `build_verification_markdown`
- `build_pr_result_markdown`
- `extract_learning_packets`
- `build_agent_md_recommendations`
- `build_validator_recommendations`
- `build_pr_comment`
- `run_pipeline`

## Completion index

### Core service files
- complete

### Test suites
- unit: present
- integration: present
- security: present
- compliance: present

### Documentation
- README: present
- runbook: present
- AGENT: present
- llms.txt: present
- manifest: present

## Final readiness checklist

- [x] core service files complete
- [x] tests present
- [x] docs present
- [x] wiring explicit
- [x] compatible with Gate + L9 services at repo-service boundary
