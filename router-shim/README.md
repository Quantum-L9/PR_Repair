# router-shim

Stateless bridge from the Python Implementer Bot to the shared
[`@quantum-l9/llm-router`](https://github.com/Quantum-L9/LLM-Router) (the
constellation's "one module, all models, zero waste" routing layer).

## Why a shim

`@quantum-l9/llm-router` is a TypeScript/ESM **library** (no CLI, no server).
The Implementer Bot is Python. `shim.mjs` is the missing invocation surface: it
reads a batch of repair requests on stdin, runs each through `L9LLMRouter`
(which owns model selection + budget), and writes results on stdout. One Node
process per PR batch — no long-lived service.

The router source is **public**, so no GitHub Packages auth is needed. Only the
provider keys are required, and only at runtime.

## Setup

```bash
cd router-shim
./setup.sh            # installs + builds the public LLM-Router from source
export OPENROUTER_API_KEY=...   # required for live calls
export PERPLEXITY_API_KEY=...   # required for search-grounded tasks
```

## Contract

Mirrors `src/pr_repair/llm/contract.py`.

**stdin** — JSON array:
```json
[{ "finding_id": "mr-1", "task_type": "code_generation", "complexity": "high",
   "system_prompt": "...", "user_prompt": "...", "client_id": "implementer-bot:owner/repo",
   "expected_output_tokens": 512 }]
```

**stdout** — JSON array:
```json
[{ "finding_id": "mr-1", "content": "{...}", "model": "...", "provider": "...",
   "total_tokens": 0, "cost": 0.0, "latency_ms": 0.0, "abstained": false, "error": null }]
```

## How the bot uses it

Enabled via `PR_FIX_LLM_ENABLED=1` (default off). When off, the bot uses
`NullLLMClient` and never spawns Node — CI and tests stay deterministic and
key-free. When on, `RouterClient` spawns `node router-shim/shim.mjs` for the
manual-review lane only; deterministic autofixes never reach the router.

Proposals are surfaced for human review (`prs/pr_<n>/llm_proposals.json`); the
bot proposes, it does not auto-merge architectural changes.
