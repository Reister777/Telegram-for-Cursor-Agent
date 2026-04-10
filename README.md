# Cursor Agent Telegram Bridge

Telegram bridge to interact with Cursor Agent from a Docker container.

## What is included

- `bot.py`: Telegram bot with short-term SQLite memory and operational commands.
- `stack.yml`: safe-by-default stack (public profile).
- `stack.safe.yml`: explicit safe profile (no `docker.sock`, restricted runtime).
- `stack.ops.yml`: operations profile (includes `docker.sock`, `/shell`, `/docker`, and `--force`).
- `.env.example`: minimum required environment variables.

## Security warnings

- `docker.sock` grants high privileges on the host; use it only if you need Docker control from Telegram.
- `agent --force`, `/shell`, and `/docker` can execute real actions.
- Always restrict access with `ALLOWED_CHAT_IDS` and use a private Telegram bot.
- Never publish `.env`, tokens, DBs, or `home/` contents (sessions, caches, transcripts).

## Requirements

- Docker or Portainer.
- Telegram bot token (`@BotFather`).
- Authorized `chat_id`.

## Environment variables (runtime)

- `TELEGRAM_BOT_TOKEN` (required)
- `ALLOWED_CHAT_IDS` (required, comma-separated list)
- `AGENT_EXTRA_ARGS` (optional, defaults to `--model gpt-5.4-medium`)
- `AGENT_TIMEOUT`, `SHELL_TIMEOUT`, `MAX_HISTORY_MESSAGES` (optional)
- `ENABLE_AGENT_FORCE` (optional, default `false`)
- `ENABLE_SHELL_COMMANDS` (optional, default `false`)
- `ENABLE_DOCKER_COMMANDS` (optional, default `false`)
- `REQUIRE_DANGEROUS_CONFIRMATION` (optional, default `true`)
- `ALLOWED_SHELL_COMMAND_PREFIXES` (optional, comma-separated command prefixes)

## Environment variables (host mounts)

`stack.yml` supports parameterized paths with compatible defaults:

- `HOST_WORK_ROOT` (default `/Volume1/Dockers`)
- `HOST_AGENT_HOME` (default `/Volume1/Dockers/cursor-agent/home`)
- `HOST_BRIDGE_CODE` (default `/Volume1/Dockers/cursor-agent`)
- `HOST_DOCKER_SOCK` (default `/var/run/docker.sock`, used by `stack.ops.yml`)

## Quick deployment

1. Copy `.env.example` to `.env` and set real values.
2. Pick a profile:
   - public/safe: `stack.safe.yml` (or `stack.yml`)
   - private/ops: `stack.ops.yml`
3. Deploy with Portainer or Docker Compose.
4. Verify the container starts and the bot responds to `/status`.

At startup, the container installs missing base tools (`python3`, `git`, `curl`, `ca-certificates`) plus Cursor Agent CLI.
The ops profile additionally installs `docker.io`.

## Telegram commands

- `/help`
- `/status`
- `/pwd`
- `/cd <path>`
- `/history`
- `/reset`
- `/shell <command>`
- `/docker <args>`

Notes:

- `/shell` is disabled unless `ENABLE_SHELL_COMMANDS=true`.
- `/docker` is disabled unless `ENABLE_DOCKER_COMMANDS=true`.
- Potentially dangerous `/shell` and `/docker` commands require `confirm ` prefix if `REQUIRE_DANGEROUS_CONFIRMATION=true`.
- Any regular message is sent to the agent with summarized memory per `chat_id`.

## Publishing to GitHub

Before publishing:

- add `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`, and minimal CI;
- confirm that `home/`, `.env`, and local artifacts are ignored by Git;
- review compliance with the CLI/model provider terms of use (Cursor).

## Versioning

This project follows Semantic Versioning (`MAJOR.MINOR.PATCH`).

- Current version is stored in `VERSION`.
- Public changes are tracked in `CHANGELOG.md`.
- Recommended release flow: bump `VERSION` + update `CHANGELOG.md` + create tag `vX.Y.Z`.
