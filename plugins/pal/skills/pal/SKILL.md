---
name: pal
description: "Use the PAL MCP with Kimi K2.7 Code as an independent second reviewer for software development: architecture, code review, debugging, pre-commit checks, security, tests, and implementation planning. Invoke with $pal when another model's critical opinion is worth the external call."
---

# PAL + Kimi

Use the bundled `pal` MCP server and its `clink` client named `kimi`, which routes Claude Code to the lower-cost Kimi K2.7 Code model ID `kimi-for-coding`. Do not select the direct `kimi-k3` PAL model unless the user explicitly asks for K3. PAL is an independent review channel, not the primary implementer or a source of truth.

## Workflow

1. Inspect the request, repository state, relevant code, diff, tests, and local instructions. Form an initial Codex assessment before asking Kimi.
2. Use `clink` with `cli_name=kimi` for Kimi reviews, including bounded questions: PAL launches Claude Code against Kimi's official Anthropic-compatible endpoint with `kimi-for-coding`, and Codex renders the result in PAL's interactive card. Use direct `chat` with `kimi-k3` only when the user explicitly requests K3.
3. Use absolute paths in file and directory fields. Pass large files by path instead of embedding them in prompts.
4. Build a self-contained context packet before a code or MR review. Maximize relevant evidence, not raw volume. State the task goal, business reason, scope, non-goals, current plan, decisions already made, unresolved questions, base/head revisions, rollout assumptions, and relevant human-review comments. Before calling Kimi, use every available task-relevant first-party connector: read GitLab discussions and pipeline results, Band threads or meeting notes, Tracker and Wiki requirements, and—when the question depends on runtime behavior—sanitized logs, metrics, stage state, or bounded database evidence. Give each external fact a source, timestamp or revision when available, and mark uncertain meeting summaries or inferred conclusions as such. Kimi does not receive direct access to those MCPs; Codex must synthesize their relevant evidence into the prompt or a sanitized local context file. Never dump unrelated history or raw secret-bearing operational data. For `clink`, pass the repository root through `working_directory_absolute_path` and relevant entry files through `absolute_file_paths`; Kimi may then use Claude Code's read-only `Read`, `Glob`, and `Grep` tools to inspect callers, tests, schemas, migrations, duplicates, and active analogues. For `chat`, attach every file or snapshot Kimi must see because direct model calls have no ambient repository access.
5. For a full implementation or MR review, explicitly ask Kimi for an adversarial symbol-by-symbol audit. Make its first and most detailed pass cover, in this order:
   - duplicated code, duplicated responsibilities, duplicate abstractions, and existing implementations that make new helpers, models, converters, methods, or files unnecessary;
   - names of every changed class, interface, method, property, local variable, constant, enum value, SQL identifier, payload field, and test, including whether each name states the domain owner, source, action, result, and side effects without ambiguity;
   - logical ownership and placement of every class and file: package, directory, layer, boundary, filename-to-declaration match, and consistency with the nearest active project analogues.

   Require repository searches and comparisons with the nearest two or three active analogues before accepting a new abstraction or proposing a rename. Ask whether one domain concept has multiple names, one name hides multiple concepts, provider vocabulary leaks past its boundary, a method name understates writes or overstates behavior, or a class is grouped by mechanism instead of domain ownership. Require an exact keep/delete/merge/rename/move verdict with concrete file/line evidence. Separate convention-backed findings from personal naming preferences. Only after this structural pass, inspect correctness, types, nullability, lifecycle, persistence, constraints, migrations, serialization, callers, transactions, concurrency, and tests. Discourage politeness, generic praise, and speculative advice.
6. Make one primary Kimi call by default. For this user's full MR or architecture-bearing backend review, use `clink`, `cli_name=kimi`, `role=codereviewer`, and the absolute repository root. For a bounded question, use the same client with `role=default`. The Kimi client is intentionally read-only; never replace its `plan` permission mode or `Read,Glob,Grep` tool allowlist with an editing or shell-enabled profile during review. Start a new Kimi session after a model change so the old model's context cache is not re-prefilled. Reuse a continuation only within the same model and task, for one focused follow-up when an important claim needs clarification.
7. Verify every Kimi claim against the code, requirements, build, tests, and project conventions. Reject generic, duplicate, unsupported, or out-of-scope findings.
8. Return the confirmed findings first, then disagreements or uncertainty, followed by the nearest useful action. Distinguish Kimi's opinion from the final Codex verdict.
9. Preserve PAL `chat` or `clink` output as a tool result so Codex can render the interactive `ui://pal/chat-review.html` card. Do not replace the call with a plain-text-only surrogate. Still provide a concise, independently verified Codex verdict after the card.

## Tool routing

- `clink`: default for this user's full repository, implementation, and MR reviews. Select `cli_name=kimi`, `role=codereviewer`, and pass `working_directory_absolute_path`; Kimi runs through Claude Code with read-only repository tools.
- `chat`: legacy direct-model route; use it with `kimi-k3` only when the user explicitly requests K3.
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
- This user has permanently authorized sharing WB organization source code, diffs, tests, schemas, internal technical documentation, and sanitized engineering logs with Kimi for PAL reviews. Do not ask for confirmation again.
- This authorization does not include credentials, secrets, personal/customer data, production dumps, or raw logs that may contain them. Redact or omit those materials.

If the PAL MCP dependency is unavailable, report that the plugin's server is not active and ask the user to check the plugin installation and required environment variables. Do not silently substitute another model.
