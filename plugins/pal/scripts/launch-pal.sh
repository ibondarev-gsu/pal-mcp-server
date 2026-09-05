#!/usr/bin/env bash
set -euo pipefail

find_uvx() {
  if command -v uvx >/dev/null 2>&1; then
    command -v uvx
    return 0
  fi

  for candidate in "$HOME/.local/bin/uvx" /opt/homebrew/bin/uvx /usr/local/bin/uvx; do
    if [[ -x "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  return 1
}

if ! uvx_bin="$(find_uvx)"; then
  echo "PAL plugin requires uvx. Install uv from https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

pal_source="${PAL_MCP_SOURCE:-$HOME/.codex/.tmp/marketplaces/pal-mcp}"
if [[ ! -f "$pal_source/pyproject.toml" ]]; then
  pal_source="git+https://github.com/ibondarev-gsu/pal-mcp-server.git@main"
fi

export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

exec "$uvx_bin" \
  --python 3.12 \
  --from "$pal_source" \
  pal-mcp-server
