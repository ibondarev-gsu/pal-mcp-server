# Kimi K3 in Codex: quick setup on another computer

This setup keeps the Kimi API key in the clone's local `.env` file and points
Codex directly at this fork. The Codex model and Kimi remain separate: Codex
orchestrates the task, while PAL calls Kimi K3 as an MCP tool.

## 1. Clone this fork

Install Git, Python 3.12+, [uv](https://docs.astral.sh/uv/), and Codex first.
Then run:

```bash
git clone --branch feat/kimi-k3-provider --single-branch \
  https://github.com/ibondarev-gsu/pal-mcp-server.git
cd pal-mcp-server

uv venv --python 3.12 .pal_venv
uv pip install --python .pal_venv/bin/python -r requirements.txt
cp .env.example .env
chmod 600 .env
```

Create a pay-as-you-go key in the Kimi API platform or a subscription key in
the Kimi Code console. Then open `.env` in an editor and set:

```env
KIMI_API_KEY=your_real_key
KIMI_ALLOWED_MODELS=kimi-k3
DEFAULT_MODEL=kimi-k3
```

Do not commit `.env` or paste the key into chat. `MOONSHOT_API_KEY` can be used
instead of `KIMI_API_KEY`. The default endpoint is
`https://api.moonshot.ai/v1`. Kimi Code subscription keys beginning with
`sk-kimi-` automatically use `https://api.kimi.com/coding/v1`; override the
endpoint with `KIMI_BASE_URL` only when needed.

## 2. Connect the local server to Codex

From the repository directory:

```bash
codex mcp remove pal 2>/dev/null || true
PAL_KIMI_DIR="$(pwd)"
codex mcp add pal -- \
  "$PAL_KIMI_DIR/.pal_venv/bin/python" \
  "$PAL_KIMI_DIR/server.py"
codex mcp get pal
```

Restart Codex after adding the server. Codex CLI and the local Codex app use
the MCP server configuration managed by `codex mcp`.

## 3. Verify

In a new Codex conversation, ask:

```text
Use PAL listmodels and verify that kimi-k3 is configured.
```

Then make a cheap smoke call:

```text
Use PAL chat with model kimi-k3 and thinking_mode=low. Ask it to reply with
exactly: kimi connection works
```

For a real backend review, keep Codex as the main implementer and call Kimi as
an independent critic, for example:

```text
Implement the task, then use PAL chat with model kimi-k3 and
thinking_mode=max to review the architecture, failure modes, concurrency,
transactions, retries, observability and tests. Recheck every valid finding
against the repository before changing code.
```

## Updating later

```bash
git pull --ff-only
uv pip install --python .pal_venv/bin/python -r requirements.txt
```

The `codex mcp` entry continues to use the same local checkout, so it does not
need to be recreated after a normal update.
