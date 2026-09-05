---
name: pal
description: "Use the PAL MCP with Kimi K3 as an independent second reviewer for software development: architecture, code review, debugging, pre-commit checks, security, tests, and implementation planning. Invoke with $pal when another model's critical opinion is worth the external call."
---

# PAL + Kimi

Use the bundled `pal` MCP server and select `kimi-k3` unless the user requests another configured model. PAL is an independent review channel, not the primary implementer or a source of truth.

## Workflow

1. Inspect the request, repository state, relevant code, diff, tests, and local instructions. Form an initial Codex assessment before asking Kimi.
2. Choose the narrowest PAL tool for the task and send only the context required to challenge that assessment.
3. Use absolute paths in file and directory fields. Pass large files by path instead of embedding them in prompts.
4. Make one primary Kimi call by default. Reuse its `continuation_id` for a focused follow-up.
5. Verify Kimi's claims against the code, requirements, build, and tests. Reject generic or unsupported findings.
6. Return the confirmed findings first, then disagreements or uncertainty, followed by the nearest useful action. Distinguish Kimi's opinion from the final Codex verdict.

## Tool routing

- `chat`: architecture choices, trade-offs, API or data-model design, and general second opinions.
- `codereview`: concrete files or diffs; check correctness, concurrency, transactions, idempotency, performance, compatibility, and maintainability.
- `precommit`: validate staged or unstaged changes against the original task before committing.
- `debug`: exceptions, failing tests, logs, races, timeouts, and root-cause analysis.
- `secaudit`: authentication, authorization, sensitive data, deserialization, injection, and other security-focused work.
- `testgen`: missing unit, integration, contract, concurrency, and failure-path tests.
- `planner`: implementation, migration, rollout, and rollback planning.
- `challenge`: adversarially stress-test an existing proposal or conclusion.
- `analyze`: explain unfamiliar architecture, dependencies, or behavior without turning the task into a general review.

If a specialized tool is unavailable, use `chat` with the same focused objective. Follow the active PAL tool schema; do not invent parameters.

## Depth and cost

- Use `thinking_mode=low` for a small, bounded question.
- Use `thinking_mode=high` for normal architecture, backend, debugging, or review work.
- Use `thinking_mode=max` only when requested or when the risk justifies the additional latency and cost.
- Prefer critical and high-severity findings over low-value style advice.

## External-data boundary

Kimi is an external provider. Explicit `$pal` invocation permits that provider call for the requested task, but it does not permit exporting organization-confidential material.

- Never send API keys, tokens, passwords, `.env` files, private certificates, customer data, production data, or unredacted secret-bearing logs.
- For public or personal repositories, send the minimum relevant files normally.
- For a private organization repository, send source files or internal logs only after the user explicitly confirms that the material may be shared with Kimi. Otherwise use a sanitized summary, public interfaces, or synthetic examples.

If the PAL MCP dependency is unavailable, report that the plugin's server is not active and ask the user to check the plugin installation and required environment variables. Do not silently substitute another model.
