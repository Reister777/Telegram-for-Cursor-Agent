# Cursor Agent Telegram Bridge

Telegram bridge to interact with Cursor Agent from a Docker container.

## What is included

- `bot.py`: Telegram bot with short-term SQLite memory and operational commands.
- `stack.yml`: Docker/Portainer stack to run the bridge + Cursor Agent CLI.
- `.env.example`: minimum required environment variables.

## Security warnings

- This project mounts `docker.sock`; this grants high privileges on the host.
- Regular messages are executed with `agent --force`; the agent can perform real actions.
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

## Environment variables (host mounts)

`stack.yml` supports parameterized paths with compatible defaults:

- `HOST_WORK_ROOT` (default `/Volume1/Dockers`)
- `HOST_AGENT_HOME` (default `/Volume1/Dockers/cursor-agent/home`)
- `HOST_BRIDGE_CODE` (default `/Volume1/Dockers/cursor-agent`)
- `HOST_DOCKER_SOCK` (default `/var/run/docker.sock`)

## Quick deployment

1. Copy `.env.example` to `.env` and set real values.
2. Deploy `stack.yml` in Portainer (or with `docker compose` if applicable).
3. Verify the container starts and the bot responds to `/status`.

At startup, the container installs (if missing): `python3`, `git`, `docker.io`, `curl`, `ca-certificates`, and Cursor Agent CLI.

## Telegram commands

- `/help`
- `/status`
- `/pwd`
- `/cd <path>`
- `/history`
- `/reset`
- `/shell <command>`
- `/docker <args>`

Any regular message is sent to the agent with summarized memory per `chat_id`.

## Publishing to GitHub

Before publishing:

- add `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`, and minimal CI;
- confirm that `home/`, `.env`, and local artifacts are ignored by Git;
- review compliance with the CLI/model provider terms of use (Cursor).
