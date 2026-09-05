"""MCP Apps UI resource and structured output helpers for external-model tools."""

import json
from collections.abc import Iterable
from typing import Any

from mcp.types import CallToolResult, TextContent

CHAT_WIDGET_URI = "ui://pal/chat-review.html"
CHAT_WIDGET_MIME_TYPE = "text/html;profile=mcp-app"


def get_chat_widget_tool_meta() -> dict[str, Any]:
    """Return portable MCP Apps metadata plus ChatGPT compatibility aliases."""

    return {
        "ui": {"resourceUri": CHAT_WIDGET_URI},
        "openai/outputTemplate": CHAT_WIDGET_URI,
        "openai/toolInvocation/invoking": "PAL вызывает внешнюю модель…",
        "openai/toolInvocation/invoked": "Ответ внешней модели готов.",
    }


def get_chat_widget_resource_meta() -> dict[str, Any]:
    """Return presentation hints for hosts that render MCP Apps resources."""

    return {
        "ui": {"prefersBorder": True},
        "openai/widgetDescription": "Shows the external model response returned by PAL chat or clink.",
        "openai/widgetPrefersBorder": True,
    }


def _visible_model_answer(content: str) -> str:
    """Remove PAL's agent-only handoff footer from the user-facing widget copy."""

    marker = "\n\n---\n\nAGENT'S TURN:"
    return content.split(marker, 1)[0].strip()


def _parse_tool_output(content: Iterable[Any]) -> dict[str, Any] | None:
    """Parse PAL's existing JSON TextContent payload without changing its fallback form."""

    for item in content:
        if not isinstance(item, TextContent):
            continue
        try:
            payload = json.loads(item.text)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(payload, dict) and "status" in payload:
            return payload
    return None


def build_chat_call_result(content: list[Any]) -> CallToolResult:
    """Add structured data for the external-model widget while preserving TextContent."""

    payload = _parse_tool_output(content)
    if payload is None:
        return CallToolResult(content=content)

    metadata = payload.get("metadata") or {}
    continuation = payload.get("continuation_offer") or {}
    raw_answer = payload.get("content")
    answer = raw_answer if isinstance(raw_answer, str) else str(raw_answer or "")
    structured_content = {
        "status": payload.get("status", "success"),
        "answer": _visible_model_answer(answer),
        "contentType": payload.get("content_type", "text"),
        "provider": metadata.get("provider_used") or metadata.get("cli_name"),
        "model": metadata.get("model_used"),
        "continuationId": continuation.get("continuation_id"),
        "remainingTurns": continuation.get("remaining_turns"),
    }
    return CallToolResult(content=content, structuredContent=structured_content)


CHAT_WIDGET_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root {
      color-scheme: light dark;
      --bg: #f7f7f8;
      --panel: rgba(255, 255, 255, 0.92);
      --text: #171717;
      --muted: #686868;
      --line: rgba(17, 17, 17, 0.10);
      --accent: #6657d9;
      --accent-soft: rgba(102, 87, 217, 0.12);
      --ok: #16845b;
      --shadow: 0 12px 36px rgba(20, 20, 30, 0.08);
    }

    @media (prefers-color-scheme: dark) {
      :root {
        --bg: #171719;
        --panel: rgba(31, 31, 35, 0.96);
        --text: #f2f2f3;
        --muted: #aaaab0;
        --line: rgba(255, 255, 255, 0.11);
        --accent: #a99fff;
        --accent-soft: rgba(169, 159, 255, 0.15);
        --ok: #54c997;
        --shadow: 0 12px 36px rgba(0, 0, 0, 0.22);
      }
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      padding: 10px;
      background: transparent;
      color: var(--text);
      font: 14px/1.5 ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    .card {
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 16px;
      background: var(--panel);
      box-shadow: var(--shadow);
    }

    .header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
      background: linear-gradient(135deg, var(--accent-soft), transparent 65%);
    }

    .identity { display: flex; align-items: center; gap: 10px; min-width: 0; }

    .mark {
      display: grid;
      width: 34px;
      height: 34px;
      place-items: center;
      flex: 0 0 auto;
      border-radius: 10px;
      color: white;
      background: linear-gradient(145deg, #6f61e8, #3f2db4);
      font-size: 12px;
      font-weight: 800;
      letter-spacing: .04em;
    }

    .title { font-size: 14px; font-weight: 720; }
    .subtitle { color: var(--muted); font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

    .status {
      display: flex;
      align-items: center;
      gap: 7px;
      flex: 0 0 auto;
      color: var(--muted);
      font-size: 12px;
    }

    .dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--accent);
      box-shadow: 0 0 0 4px var(--accent-soft);
      animation: pulse 1.4s ease-in-out infinite;
    }

    .ready .dot { background: var(--ok); animation: none; }
    .error .dot { background: #d84b4b; animation: none; }

    @keyframes pulse { 50% { opacity: .45; transform: scale(.82); } }

    .meta {
      display: none;
      gap: 7px;
      padding: 11px 16px 0;
      flex-wrap: wrap;
    }

    .meta.visible { display: flex; }

    .chip {
      padding: 3px 8px;
      border: 1px solid var(--line);
      border-radius: 999px;
      color: var(--muted);
      background: var(--bg);
      font-size: 11px;
    }

    .body { padding: 14px 16px 16px; }

    .answer {
      margin: 0;
      max-height: 430px;
      overflow: auto;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      color: var(--text);
      font: 13px/1.58 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }

    .placeholder { color: var(--muted); font-family: inherit; }

    .footer {
      display: none;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-top: 14px;
      padding-top: 12px;
      border-top: 1px solid var(--line);
    }

    .footer.visible { display: flex; }
    .continuation { min-width: 0; color: var(--muted); font-size: 11px; overflow: hidden; text-overflow: ellipsis; }

    button {
      border: 1px solid var(--line);
      border-radius: 9px;
      padding: 6px 10px;
      color: var(--text);
      background: var(--bg);
      cursor: pointer;
      font: inherit;
      font-size: 12px;
    }

    button:hover { border-color: var(--accent); }
  </style>
</head>
<body>
  <section class="card" id="card" aria-live="polite">
    <header class="header">
      <div class="identity">
        <div class="mark">PAL</div>
        <div>
          <div class="title">Проверка внешней моделью</div>
          <div class="subtitle" id="subtitle">Ожидаем результат PAL</div>
        </div>
      </div>
      <div class="status" id="status"><span class="dot"></span><span id="statusText">Анализирует…</span></div>
    </header>
    <div class="meta" id="meta"></div>
    <main class="body">
      <pre class="answer placeholder" id="answer">Ответ появится здесь, когда внешняя модель закончит работу.</pre>
      <div class="footer" id="footer">
        <div class="continuation" id="continuation"></div>
        <button type="button" id="copy">Копировать ответ</button>
      </div>
    </main>
  </section>

  <script>
    const card = document.getElementById("card");
    const subtitle = document.getElementById("subtitle");
    const statusText = document.getElementById("statusText");
    const meta = document.getElementById("meta");
    const answer = document.getElementById("answer");
    const footer = document.getElementById("footer");
    const continuation = document.getElementById("continuation");
    const copyButton = document.getElementById("copy");
    let latestAnswer = "";

    function displayName(value) {
      if (!value) return "";
      const text = String(value);
      return text.charAt(0).toUpperCase() + text.slice(1);
    }

    function addChip(label, value) {
      if (value === undefined || value === null || value === "") return;
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.textContent = `${label}: ${value}`;
      meta.appendChild(chip);
    }

    function render(raw) {
      const envelope = raw || {};
      const data = envelope.structuredContent || envelope;
      if (!data || typeof data !== "object") return;

      const failed = data.status === "error";
      card.classList.remove("ready", "error");
      card.classList.add(failed ? "error" : "ready");
      statusText.textContent = failed ? "Ошибка" : "Готово";

      const provider = displayName(data.provider || "Внешняя модель");
      subtitle.textContent = data.model ? `${provider} · ${data.model}` : provider;

      meta.replaceChildren();
      addChip("Провайдер", provider);
      addChip("Модель", data.model);
      addChip("Статус", data.status);
      meta.classList.toggle("visible", meta.childElementCount > 0);

      latestAnswer = String(data.answer || "Модель не вернула текстовый ответ.");
      answer.textContent = latestAnswer;
      answer.classList.remove("placeholder");

      if (data.continuationId) {
        const turns = Number.isInteger(data.remainingTurns) ? ` · осталось ходов: ${data.remainingTurns}` : "";
        continuation.textContent = `Продолжение: ${data.continuationId}${turns}`;
      } else {
        continuation.textContent = "";
      }
      footer.classList.add("visible");
    }

    function renderInput(raw) {
      const data = raw?.arguments || raw || {};
      if (!data || typeof data !== "object") return;
      const model = String(data.model || data.cli_name || "внешняя модель");
      subtitle.textContent = model.toLowerCase().startsWith("kimi") ? `Kimi · ${model}` : model;
      statusText.textContent = "Анализирует…";
    }

    window.addEventListener("message", (event) => {
      if (event.source !== window.parent) return;
      const message = event.data;
      if (!message || message.jsonrpc !== "2.0") return;
      if (message.method === "ui/notifications/tool-input") renderInput(message.params);
      if (message.method === "ui/notifications/tool-result") render(message.params);
      if (message.method === "ui/initialize") render(message.params?.toolResult || message.params);
    }, { passive: true });

    if (window.openai?.toolOutput) render(window.openai.toolOutput);

    copyButton.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(latestAnswer);
        copyButton.textContent = "Скопировано";
      } catch (_) {
        const range = document.createRange();
        range.selectNodeContents(answer);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
        copyButton.textContent = "Выделено";
      }
      setTimeout(() => { copyButton.textContent = "Копировать ответ"; }, 1400);
    });
  </script>
</body>
</html>
"""
