# Security Policy

## Reporting vulnerabilities

If you find a security vulnerability, do not open a public issue with exploitable details.

Preferred private reporting channel:

- Telegram: `@Reister`

Please include:

- Problem description.
- Expected impact.
- Reproduction steps.
- Affected version/commit.

## Scope and known risks

This project can execute system and Docker commands (`docker.sock`) from Telegram.
By design, this implies a high privilege level on the host.

Minimum required safeguards:

- Configure `ALLOWED_CHAT_IDS`.
- Keep `TELEGRAM_BOT_TOKEN` secret.
- Run only in trusted networks or behind access controls.

## Secret management

- Never commit `.env`, tokens, `auth.json`, or session databases.
- Rotate credentials immediately if exposure is suspected.
