// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
// Build the SDK first. Credentials are supplied through the environment, never CLI arguments.
import { GovernanceRuntimeClient, isCompleted } from "../dist/governance.js";
import { pathToFileURL } from "node:url";

export async function runGovernedCall({ baseUrl, apiKey, name, purpose, arguments: args = {} }) {
  const client = new GovernanceRuntimeClient({ baseUrl, apiKey, timeout: 5000 });
  const result = await client.callTool(name, args, purpose);
  // Completion is positive evidence, not the absence of an error.
  return {
    completed: isCompleted(result),
    denied: result.error === "governance_denied",
    requiresApproval: result.error === "governance_approval_required",
    uncertain: result.error === "governance_unknown_outcome"
      || result.outcome_status === "UNKNOWN" || result.status === "UNKNOWN",
    approvalId: typeof result.approval_id === "string" ? result.approval_id : null,
  };
}

if (process.argv[1] && !process.argv[1].startsWith("file:")
    && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    if (!process.env.WHITEPACT_API_KEY || !process.env.WHITEPACT_TOOL)
      throw new Error("Missing local configuration");
    console.log(JSON.stringify(await runGovernedCall({
      baseUrl: process.env.WHITEPACT_URL ?? "http://127.0.0.1:8765",
      apiKey: process.env.WHITEPACT_API_KEY,
      name: process.env.WHITEPACT_TOOL,
      purpose: process.env.WHITEPACT_PURPOSE ?? "sdk-governance",
    })));
  } catch {
    console.error("Request did not produce a confirmed answer. Do not retry a mutation; reconcile first.");
    process.exitCode = 1;
  }
}
