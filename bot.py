#!/usr/bin/env python3
"""Telegram bridge for Cursor Agent running inside the same container."""

from __future__ import annotations

import html
import json
import logging
import os
import shlex
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable
from urllib import error, parse, request


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"Missing required env var: {name}")
    return value


TOKEN = required_env("TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_IDS = {
    int(part.strip())
    for part in os.getenv("ALLOWED_CHAT_IDS", "").split(",")
    if part.strip()
}

if not ALLOWED_CHAT_IDS:
    raise SystemExit("ALLOWED_CHAT_IDS must contain at least one chat id")

API_BASE = f"https://api.telegram.org/bot{TOKEN}"
WORK_ROOT = Path(os.getenv("WORK_ROOT", "/work")).resolve()
STATE_DB_PATH = Path(
    os.getenv("STATE_DB_PATH", os.path.join(os.getenv("HOME", "/home/dev"), ".cursor-telegram", "state.db"))
)
AGENT_CMD = os.getenv("AGENT_CMD", "agent")
AGENT_EXTRA_ARGS = shlex.split(os.getenv("AGENT_EXTRA_ARGS", "-p --output-format text"))
AGENT_TIMEOUT = int(os.getenv("AGENT_TIMEOUT", "3600"))
SHELL_TIMEOUT = int(os.getenv("SHELL_TIMEOUT", "300"))
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "24"))
TELEGRAM_POLL_TIMEOUT = int(os.getenv("TELEGRAM_POLL_TIMEOUT", "30"))
TELEGRAM_CHUNK_SIZE = int(os.getenv("TELEGRAM_CHUNK_SIZE", "3900"))
MEMORY_TEXT_LIMIT = int(os.getenv("MEMORY_TEXT_LIMIT", "1800"))


def resolve_allowed_path(raw_path: str, base: Path | None = None, must_exist: bool = True) -> Path:
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = (base or WORK_ROOT) / candidate

    resolved = candidate.resolve()
    root = WORK_ROOT.resolve()

    if resolved != root and root not in resolved.parents:
        raise ValueError(f"Path outside WORK_ROOT: {resolved}")

    if must_exist and not resolved.exists():
        raise ValueError(f"Path does not exist: {resolved}")

    if must_exist and not resolved.is_dir():
        raise ValueError(f"Path is not a directory: {resolved}")

    return resolved


DEFAULT_WORKDIR = resolve_allowed_path(os.getenv("DEFAULT_WORKDIR", str(WORK_ROOT)))


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)


STATE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DB = sqlite3.connect(STATE_DB_PATH)
DB.row_factory = sqlite3.Row


def init_db() -> None:
    DB.execute(
        """
        CREATE TABLE IF NOT EXISTS session_state (
            chat_id INTEGER PRIMARY KEY,
            cwd TEXT NOT NULL
        )
        """
    )
    DB.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at INTEGER NOT NULL
        )
        """
    )
    DB.execute(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    DB.commit()


def get_meta(key: str, default: str = "") -> str:
    row = DB.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_meta(key: str, value: str) -> None:
    DB.execute(
        """
        INSERT INTO meta(key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )
    DB.commit()


def get_cwd(chat_id: int) -> Path:
    row = DB.execute("SELECT cwd FROM session_state WHERE chat_id = ?", (chat_id,)).fetchone()
    if not row:
        DB.execute(
            "INSERT INTO session_state(chat_id, cwd) VALUES (?, ?)",
            (chat_id, str(DEFAULT_WORKDIR)),
        )
        DB.commit()
        return DEFAULT_WORKDIR

    try:
        return resolve_allowed_path(row["cwd"])
    except ValueError:
        set_cwd(chat_id, DEFAULT_WORKDIR)
        return DEFAULT_WORKDIR


def set_cwd(chat_id: int, cwd: Path) -> None:
    DB.execute(
        """
        INSERT INTO session_state(chat_id, cwd)
        VALUES (?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET cwd = excluded.cwd
        """,
        (chat_id, str(cwd)),
    )
    DB.commit()


def trim_for_memory(text: str, limit: int = MEMORY_TEXT_LIMIT) -> str:
    cleaned = " ".join(text.strip().split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3] + "..."


def append_message(chat_id: int, role: str, content: str) -> None:
    DB.execute(
        "INSERT INTO messages(chat_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (chat_id, role, trim_for_memory(content), int(time.time())),
    )
    DB.execute(
        """
        DELETE FROM messages
        WHERE chat_id = ?
          AND id NOT IN (
              SELECT id
              FROM messages
              WHERE chat_id = ?
              ORDER BY id DESC
              LIMIT ?
          )
        """,
        (chat_id, chat_id, MAX_HISTORY_MESSAGES),
    )
    DB.commit()


def clear_history(chat_id: int) -> None:
    DB.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
    DB.commit()


def load_history(chat_id: int, limit: int) -> list[sqlite3.Row]:
    rows = DB.execute(
        """
        SELECT role, content
        FROM messages
        WHERE chat_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (chat_id, limit),
    ).fetchall()
    return list(reversed(rows))


def telegram_api(method: str, payload: dict) -> dict:
    encoded_payload = {}
    for key, value in payload.items():
        if isinstance(value, (dict, list)):
            encoded_payload[key] = json.dumps(value)
        else:
            encoded_payload[key] = value

    body = parse.urlencode(encoded_payload, doseq=True).encode()
    req = request.Request(f"{API_BASE}/{method}", data=body)

    with request.urlopen(req, timeout=TELEGRAM_POLL_TIMEOUT + 15) as response:
        data = json.loads(response.read().decode("utf-8"))

    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error for {method}: {data}")

    return data["result"]


def send_chat_action(chat_id: int, action: str) -> None:
    try:
        telegram_api("sendChatAction", {"chat_id": chat_id, "action": action})
    except Exception as exc:  # pragma: no cover - best effort only
        logging.warning("Could not send chat action: %s", exc)


def looks_like_markdown_table(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return False

    table_like = sum(1 for line in lines if line.startswith("|") and line.endswith("|"))
    separator_like = sum(
        1
        for line in lines
        if set(line.replace("|", "").replace("-", "").replace(":", "").replace(" ", "")) == set()
    )

    return table_like >= 2 or (table_like >= 1 and separator_like >= 1)


def strip_fenced_code_markers(text: str) -> str:
    lines = text.splitlines()
    if not lines:
        return text

    if lines[0].strip().startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1])

    return text.replace("```", "")


def should_render_as_pre(text: str) -> bool:
    lines = [line for line in text.splitlines() if line.strip()]
    if "```" in text:
        return True
    if looks_like_markdown_table(text):
        return True
    if len(lines) >= 8:
        return True
    if any(line.startswith("    ") or line.startswith("\t") for line in lines):
        return True
    return False


def format_for_telegram_html(text: str) -> tuple[str, str | None]:
    normalized = text.replace("\r\n", "\n").strip()
    if not normalized:
        return "(no output)", None

    if should_render_as_pre(normalized):
        pre_text = strip_fenced_code_markers(normalized)
        return f"<pre>{html.escape(pre_text)}</pre>", "HTML"

    escaped = html.escape(normalized)
    return escaped, "HTML"


def chunk_text(text: str, limit: int) -> Iterable[str]:
    remaining = text.strip()
    if not remaining:
        yield "(no output)"
        return

    while len(remaining) > limit:
        split_at = remaining.rfind("\n", 0, limit)
        if split_at <= 0:
            split_at = limit
        yield remaining[:split_at]
        remaining = remaining[split_at:].lstrip("\n")

    if remaining:
        yield remaining


def send_text(chat_id: int, text: str) -> None:
    parts = list(chunk_text(text, TELEGRAM_CHUNK_SIZE))
    total = len(parts)

    for index, part in enumerate(parts, start=1):
        prefix = f"[{index}/{total}]\n" if total > 1 else ""
        raw_message = prefix + part
        formatted, parse_mode = format_for_telegram_html(raw_message)

        try:
            payload = {
                "chat_id": chat_id,
                "text": formatted,
                "disable_web_page_preview": True,
            }
            if parse_mode:
                payload["parse_mode"] = parse_mode
            telegram_api("sendMessage", payload)
        except Exception as exc:
            logging.warning("Falling back to plain Telegram text: %s", exc)
            telegram_api(
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": raw_message,
                    "disable_web_page_preview": True,
                },
            )


def run_process(command: list[str], cwd: Path, timeout: int) -> tuple[int, str]:
    env = os.environ.copy()
    env["HOME"] = os.getenv("HOME", "/home/dev")
    env["PATH"] = os.getenv(
        "PATH",
        "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/home/dev/.local/bin",
    )

    completed = subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    combined = stdout
    if stderr:
        combined = f"{combined}\n\n[stderr]\n{stderr}".strip()

    if not combined:
        combined = "(no output)"

    return completed.returncode, combined


def build_agent_prompt(chat_id: int, current_dir: Path, user_prompt: str) -> str:
    transcript_lines = []
    for row in load_history(chat_id, MAX_HISTORY_MESSAGES):
        speaker = "User" if row["role"] == "user" else "Assistant"
        transcript_lines.append(f"{speaker}: {row['content']}")

    transcript = "\n".join(transcript_lines) if transcript_lines else "(no history)"

    return f"""
You keep a persistent session with summarized memory from Telegram.
Reply in English unless the user asks for another language.
Current working directory: {current_dir}
Main root: {WORK_ROOT}
You can access NAS Docker from this container.
When asked for current Docker/service/container/file/system status, use real commands to verify it.
Do not invent current states or reuse old data as if it were live.
If a command or call fails, clearly state it failed and include the error.
Do not claim that a call was blocked by the environment unless you just tried it and it actually failed.
Do not run destructive actions on Docker, files, or the system without explicit and concrete user instruction.
In Telegram avoid Markdown tables. Prefer clear lists and, if you need aligned columns or long outputs, use text blocks that render reliably.
If you make changes or execute actions, summarize the result at the end.

Recent history:
{transcript}

New user message:
{user_prompt}
""".strip()


def handle_agent(chat_id: int, text: str) -> None:
    cwd = get_cwd(chat_id)
    prompt = build_agent_prompt(chat_id, cwd, text)
    send_chat_action(chat_id, "typing")

    exit_code, output = run_process([AGENT_CMD, *AGENT_EXTRA_ARGS, prompt], cwd, AGENT_TIMEOUT)
    append_message(chat_id, "user", text)
    append_message(chat_id, "assistant", output)

    if exit_code != 0:
        send_text(chat_id, f"[agent exit={exit_code}]\n{output}")
        return

    send_text(chat_id, output)


def handle_shell(chat_id: int, command_text: str) -> None:
    if not command_text.strip():
        send_text(chat_id, "Usage: /shell <command>")
        return

    cwd = get_cwd(chat_id)
    send_chat_action(chat_id, "typing")
    exit_code, output = run_process(["bash", "-lc", command_text], cwd, SHELL_TIMEOUT)
    append_message(chat_id, "user", f"/shell {command_text}")
    append_message(chat_id, "assistant", f"[shell exit={exit_code}] {output}")
    send_text(chat_id, f"[shell exit={exit_code}]\n{output}")


def handle_docker(chat_id: int, command_text: str) -> None:
    if not command_text.strip():
        send_text(chat_id, "Usage: /docker <args>. Example: /docker ps")
        return

    cwd = get_cwd(chat_id)
    send_chat_action(chat_id, "typing")

    try:
        docker_args = shlex.split(command_text)
    except ValueError as exc:
        send_text(chat_id, f"Could not parse docker command: {exc}")
        return

    exit_code, output = run_process(["docker", *docker_args], cwd, SHELL_TIMEOUT)
    append_message(chat_id, "user", f"/docker {command_text}")
    append_message(chat_id, "assistant", f"[docker exit={exit_code}] {output}")
    send_text(chat_id, f"[docker exit={exit_code}]\n{output}")


def handle_cd(chat_id: int, target: str) -> None:
    if not target.strip():
        send_text(chat_id, "Usage: /cd <subdirectory inside /work>")
        return

    current = get_cwd(chat_id)

    try:
        new_cwd = resolve_allowed_path(target.strip(), base=current)
    except ValueError as exc:
        send_text(chat_id, str(exc))
        return

    set_cwd(chat_id, new_cwd)
    send_text(chat_id, f"CWD updated to:\n{new_cwd}")


def handle_status(chat_id: int) -> None:
    cwd = get_cwd(chat_id)
    history_count = DB.execute(
        "SELECT COUNT(*) AS count FROM messages WHERE chat_id = ?",
        (chat_id,),
    ).fetchone()["count"]

    git_branch = "(sin repo git)"
    try:
        exit_code, output = run_process(["git", "branch", "--show-current"], cwd, 5)
        if exit_code == 0 and output.strip():
            git_branch = output.strip()
    except Exception:
        pass

    docker_state = "disponible"
    try:
        exit_code, output = run_process(["docker", "version", "--format", "{{.Server.Version}}"], cwd, 10)
        if exit_code == 0 and output.strip() != "(no output)":
            docker_state = output.strip()
    except Exception:
        docker_state = "no comprobado"

    send_text(
        chat_id,
        "\n".join(
            [
                "Current status:",
                f"- cwd: {cwd}",
                f"- work_root: {WORK_ROOT}",
                f"- git: {git_branch}",
                f"- docker: {docker_state}",
                f"- history: {history_count} messages",
                f"- agent_cmd: {AGENT_CMD}",
            ]
        ),
    )


def handle_history(chat_id: int) -> None:
    rows = load_history(chat_id, 8)
    if not rows:
        send_text(chat_id, "No saved history.")
        return

    lines = []
    for row in rows:
        speaker = "U" if row["role"] == "user" else "A"
        lines.append(f"{speaker}: {row['content']}")

    send_text(chat_id, "Recent history:\n" + "\n".join(lines))


def handle_help(chat_id: int) -> None:
    send_text(
        chat_id,
        "\n".join(
            [
                "Available commands:",
                "/help - show this help",
                "/status - bridge status",
                "/pwd - show current directory",
                "/cd <path> - change directory inside /work",
                "/history - show short saved history",
                "/reset - clear session memory",
                "/shell <command> - run bash inside container",
                "/docker <args> - run docker through docker.sock",
                "",
                "Any regular message is sent to agent with memory.",
            ]
        ),
    )


def process_message(chat_id: int, text: str) -> None:
    text = text.strip()
    if not text:
        send_text(chat_id, "Send text or a /help command.")
        return

    command, _, argument = text.partition(" ")

    if command in {"/help", "/start"}:
        handle_help(chat_id)
    elif command == "/status":
        handle_status(chat_id)
    elif command == "/pwd":
        send_text(chat_id, str(get_cwd(chat_id)))
    elif command == "/cd":
        handle_cd(chat_id, argument)
    elif command == "/history":
        handle_history(chat_id)
    elif command == "/reset":
        clear_history(chat_id)
        send_text(chat_id, "History cleared for this session.")
    elif command == "/shell":
        handle_shell(chat_id, argument)
    elif command == "/docker":
        handle_docker(chat_id, argument)
    else:
        handle_agent(chat_id, text)


def poll_updates(offset: int) -> list[dict]:
    return telegram_api(
        "getUpdates",
        {
            "offset": offset,
            "timeout": TELEGRAM_POLL_TIMEOUT,
            "allowed_updates": ["message"],
        },
    )


def main() -> None:
    init_db()
    offset = int(get_meta("last_update_id", "0"))
    logging.info("Telegram bridge started. Allowed chats: %s", sorted(ALLOWED_CHAT_IDS))

    while True:
        try:
            updates = poll_updates(offset)
            for update in updates:
                offset = update["update_id"] + 1
                set_meta("last_update_id", str(offset))

                message = update.get("message") or {}
                chat = message.get("chat") or {}
                chat_id = chat.get("id")
                text = message.get("text")

                if chat_id not in ALLOWED_CHAT_IDS:
                    continue

                if not text:
                    send_text(chat_id, "I only process text messages.")
                    continue

                logging.info("Handling message from %s: %s", chat_id, text[:120])
                process_message(chat_id, text)

        except error.HTTPError as exc:
            logging.exception("HTTP error while talking to Telegram: %s", exc)
            time.sleep(5)
        except subprocess.TimeoutExpired as exc:
            logging.exception("Subprocess timeout: %s", exc)
            if ALLOWED_CHAT_IDS:
                for chat_id in ALLOWED_CHAT_IDS:
                    try:
                        send_text(chat_id, "Una tarea ha excedido el timeout configurado.")
                    except Exception:
                        logging.exception("Could not notify timeout to %s", chat_id)
            time.sleep(2)
        except Exception as exc:  # pragma: no cover - long running guard
            logging.exception("Unexpected bridge error: %s", exc)
            time.sleep(5)


if __name__ == "__main__":
    main()
