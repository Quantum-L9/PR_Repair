#!/usr/bin/env bash
# Build the router-shim and its public LLM-Router dependency.
#
# The @quantum-l9/llm-router package ships TypeScript source with no `prepare`
# hook, so installing it from the (public) git repo does NOT auto-build dist/.
# We install it and then compile it in place so shim.mjs can import dist/index.js.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$here"

echo "[router-shim] installing dependencies..."
npm install

dep_dir="node_modules/@quantum-l9/llm-router"
if [ ! -f "$dep_dir/dist/index.js" ]; then
  echo "[router-shim] building @quantum-l9/llm-router from source..."
  (cd "$dep_dir" && npm install && npm run build)
fi

echo "[router-shim] ready. Provider keys are read from the environment at runtime:"
echo "  OPENROUTER_API_KEY, PERPLEXITY_API_KEY"
