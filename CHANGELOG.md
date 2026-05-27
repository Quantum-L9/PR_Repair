# Changelog

## v3

- Removed generated caches and bytecode artifacts.
- Preserved validated V2 behavior and tests.
- Added explicit rollback package boundary as a compatibility surface over validated workspace rollback implementation.
- Regenerated canonical docs for a single repo identity.
- Regenerated manifest from actual filesystem state.
- Regenerated validation report from executed checks.

## v2

- Restored clustering and candidate generation from the original pack.
- Preserved ingestion and normalization layers.
- Removed bundle recursion from the clean pack.

## v1

- Consolidated PR repair bundles into a canonical repository pack.
