# Kimi K2.7 Code in Codex: install the PAL plugin

The Codex plugin is the supported setup for this fork. It installs the PAL MCP
tools and the `$pal` skill together, so a new computer does not need a manual
checkout, virtual environment, or separate `codex mcp add` entry.

Codex remains the primary agent. PAL calls Kimi K2.7 Code as an independent reviewer.

## Prerequisites

Install:

- [Codex](https://developers.openai.com/codex/)
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code/getting-started) for repository-aware Kimi agent reviews
- Git
- [uv](https://docs.astral.sh/uv/getting-started/installation/), which provides `uvx`

Create either a pay-as-you-go Kimi API key or a Kimi Code subscription key.
Never commit the key or paste it into a chat.

## 1. Remove an older standalone PAL entry

Skip this step if PAL has never been configured on the computer. Otherwise,
check for the old MCP entry:

```bash
codex mcp get pal
```

If it exists, remove it before installing the plugin so Codex does not load two
MCP servers with the same `pal` name:

```bash
codex mcp remove pal
```

## 2. Install the plugin

Add this repository as a Git marketplace, then install PAL:

```bash
codex plugin marketplace add ibondarev-gsu/pal-mcp-server --ref main
codex plugin add pal@pal-mcp
```

The same flow is available in the Codex app under **Plugins → Add**: add the
GitHub repository `https://github.com/ibondarev-gsu/pal-mcp-server`, then install
**PAL + Kimi** from the **PAL MCP** marketplace.

The plugin launches the server with `uvx` directly from this fork. Dependency
installation and isolation are automatic on first use.

## 3. Configure Kimi

Open the installed plugin's PAL MCP settings in Codex and provide:

```env
KIMI_API_KEY=your_real_key
KIMI_CLAUDE_API_KEY=your_kimi_code_console_key
```

`MOONSHOT_API_KEY` can be used instead of `KIMI_API_KEY`. The default endpoint
is `https://api.moonshot.ai/v1`. Subscription keys beginning with `sk-kimi-`
automatically use `https://api.kimi.com/coding/v1`; set `KIMI_BASE_URL` only
when an explicit override is required.

`KIMI_CLAUDE_API_KEY` is used only by the `clink` client named `kimi`. It must
be a key from the Kimi Code Console. PAL passes it to the child Claude Code
process as `ANTHROPIC_API_KEY` without writing it to Claude's global settings.
If `KIMI_CLAUDE_API_KEY` is omitted, the client falls back to `KIMI_API_KEY`.
That fallback works only when the latter is also a Kimi Code key.

The bundled client follows Kimi's official Claude Code configuration:
`ANTHROPIC_BASE_URL=https://api.kimi.com/coding/`, model `kimi-for-coding`
(Kimi K2.7 Code), thinking enabled, and a 262144-token context. It launches Claude Code with `--bare`, disables
global/project/local settings for that child process, uses plan permissions,
and enables only `Read`, `Glob`, and `Grep`. It can inspect a repository but
cannot edit files or run shell commands, and it does not disturb another
provider configured in the user's normal Claude settings.

After installation or configuration changes, fully quit Codex and start a new
task. Existing tasks keep the skill and tool inventory they started with.

## 4. Use the bundled skill

Invoke `$pal` explicitly whenever Kimi should participate. The skill selects
the `clink` client named `kimi`, which uses `kimi-for-coding`, and requires
Codex to verify the external model's findings. It does not select the direct
`kimi-k3` model unless the user explicitly asks for K3.

Start with this smoke test:

```text
Use $pal. Call pal.clink with cli_name=kimi, role=default, and the absolute
repository path. Ask it to reply exactly: PAL_UI_OK
```

Then verify repository-aware review in a trusted checkout:

```text
Use $pal. Call pal.clink with cli_name=kimi, role=codereviewer, and the absolute
repository path. Ask Kimi to inspect naming, duplication, and package placement.
```

Useful examples:

```text
$pal review this diff with Kimi K2.7 Code and verify every finding locally

$pal challenge this implementation plan, focusing on concurrency and rollback

$pal debug this failure with Kimi K2.7 Code
```

Start a new Kimi session after switching model IDs. Kimi documents that model
switches invalidate the existing context cache and can temporarily increase
usage by re-prefilling the prior context.

Kimi is an external provider. Do not send secrets, customer data, production
data, or private organization source code unless sharing that material with
Kimi has been explicitly approved.

## UI behavior

`pal.chat` and `pal.clink` expose an MCP Apps result card with the provider,
model, answer, continuation ID, and copy action. Other PAL tools return their
normal text result.

If the card or `$pal` is missing:

1. Confirm that **PAL + Kimi** is installed and enabled.
2. Fully quit Codex, not just its window.
3. Start a new task and repeat the smoke test.

## Updating

Refresh the Git marketplace and reinstall the current plugin version:

```bash
codex plugin marketplace upgrade pal-mcp
codex plugin add pal@pal-mcp
```

Then restart Codex and use a new task so it receives the updated skill, MCP
tools, and UI metadata.

## Development checkout

Cloning the repository is necessary only when changing PAL itself:

```bash
git clone --branch main --single-branch \
  https://github.com/ibondarev-gsu/pal-mcp-server.git
cd pal-mcp-server

uv venv --python 3.12 .pal_venv
uv pip install --python .pal_venv/bin/python -r requirements.txt
cp .env.example .env
chmod 600 .env
```

For normal Codex use, install the plugin instead of registering this checkout
with `codex mcp add`.
