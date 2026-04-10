# Changelog

## Unreleased

- Fixed ops startup resilience in `stack.ops.yml` by adding `dpkg --configure -a` and `apt-get -f install -y` preflight recovery to avoid bootloops after interrupted package operations.
- Added `VERSION` file and documented Semantic Versioning workflow in `README.md`.
- Added runtime hardening controls in `bot.py`: `ENABLE_SHELL_COMMANDS`, `ENABLE_DOCKER_COMMANDS`, `ENABLE_AGENT_FORCE`, dangerous-command confirmation, and shell prefix allowlist.
- Added profile-based stacks: `stack.safe.yml` and `stack.ops.yml`.
- Changed `stack.yml` to safe defaults (no `docker.sock`, no `--force`, no `/shell` or `/docker` by default).
- Updated docs and examples for safe vs ops deployment profiles.
- Set a fixed CLI model in `stack.yml` with `--model gpt-5.4-medium` in `AGENT_EXTRA_ARGS` so the Telegram bridge does not rely only on `auto`.
- Added `stack.yml` for Portainer with Cursor Agent, Telegram bridge, and Docker socket access.
- Added `bot.py` with Telegram polling, SQLite memory, shell commands, Docker commands, and `agent` chat mode.
- Added `README.md` and `.env.example` with deployment notes and required variables.
- Changed normal chat mode to run `agent` with `--force` to allow live Docker/NAS checks.
- Tightened the session prompt to prioritize live verification and avoid presenting stale state as current.
- Improved Telegram rendering by sending HTML and wrapping long/tabular outputs in `<pre>` blocks.
- Open-source preparation: parameterized host mounts in `stack.yml`, strengthened `README.md` security guidance, and added OSS metadata (`LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `PROJECT_MAP.md`, `.editorconfig`, `.gitignore`, minimal CI).
- Translated project content to English (documentation and user-facing bot text).
