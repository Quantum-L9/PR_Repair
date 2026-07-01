#!/usr/bin/env node
// L9 Implementer Bot <-> LLM-Router bridge (stateless subprocess shim).
//
// Reads a JSON array of repair requests on stdin, runs each through the shared
// @quantum-l9/llm-router (which owns model selection + budget), and writes a JSON
// array of results on stdout. One process invocation handles a whole PR's batch.
//
// Contract (must match src/pr_repair/llm/contract.py):
//   in : [{ finding_id, task_type, complexity, system_prompt, user_prompt,
//           client_id, expected_output_tokens }]
//   out: [{ finding_id, content, model, provider, total_tokens, cost,
//           latency_ms, abstained, error }]
//
// The router source is public (github.com/Quantum-L9/LLM-Router). See README.md
// for how to vendor + build it. Provider keys (OPENROUTER_API_KEY /
// PERPLEXITY_API_KEY) are read from the environment at deploy time.

import { L9LLMRouter, TaskType, TaskComplexity } from "@quantum-l9/llm-router";

const COMPLEXITY = {
  trivial: TaskComplexity.TRIVIAL,
  low: TaskComplexity.LOW,
  medium: TaskComplexity.MEDIUM,
  high: TaskComplexity.HIGH,
  critical: TaskComplexity.CRITICAL,
};

const TASK_TYPE = {
  code_generation: TaskType.CODE_GENERATION,
};

async function readStdin() {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  return Buffer.concat(chunks).toString("utf8");
}

function buildRouter() {
  return new L9LLMRouter({
    appName: "l9-implementer-bot",
    openrouterApiKey: process.env.OPENROUTER_API_KEY,
    perplexityApiKey: process.env.PERPLEXITY_API_KEY,
  });
}

async function runOne(router, req) {
  const seenClients = buildRouter._clients ?? (buildRouter._clients = new Set());
  const clientId = req.client_id || "implementer-bot";
  if (!seenClients.has(clientId)) {
    router.initClient(clientId);
    seenClients.add(clientId);
  }
  // Optional tier/depth/effort hints (ADR 0001) relayed as-is. The shim does not
  // interpret them; L9LLMRouter.execute is the acceptance authority.
  const task = {
    type: TASK_TYPE[req.task_type] ?? TaskType.CODE_GENERATION,
    complexity: COMPLEXITY[req.complexity] ?? TaskComplexity.MEDIUM,
    expectedOutputTokens: req.expected_output_tokens ?? undefined,
    requiresReasoning: true,
    clientId,
    depth: req.depth ?? undefined,
    reasoningEffort: req.effort ?? undefined,
    modelTier: req.tier ?? undefined,
  };
  try {
    const res = await router.execute(task, req.system_prompt, req.user_prompt);
    return {
      finding_id: req.finding_id,
      content: res.content ?? "",
      model: res.model ?? "",
      provider: res.provider ?? "",
      total_tokens: res.totalTokens ?? 0,
      cost: res.cost ?? 0,
      latency_ms: res.latencyMs ?? 0,
      abstained: false,
      error: null,
    };
  } catch (err) {
    return {
      finding_id: req.finding_id,
      content: "",
      abstained: true,
      error: String(err?.message ?? err),
    };
  }
}

async function main() {
  const raw = await readStdin();
  const requests = JSON.parse(raw || "[]");
  if (!Array.isArray(requests)) throw new Error("input must be a JSON array");
  const router = buildRouter();
  const out = [];
  for (const req of requests) out.push(await runOne(router, req));
  process.stdout.write(JSON.stringify(out));
}

main().catch((err) => {
  process.stderr.write(String(err?.stack ?? err));
  process.exit(1);
});
