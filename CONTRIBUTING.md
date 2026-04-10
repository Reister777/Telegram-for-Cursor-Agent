# Contributing

Thank you for contributing to this project.

## Recommended workflow

1. Create a branch from `main`.
2. Keep changes small and focused.
3. Update documentation if behavior changes.
4. Run local checks before opening a PR.
5. Clearly describe the operational impact of your change.

## Security rules

- Do not upload secrets (`.env`, tokens, credentials, sessions).
- Do not include `home/` content or agent transcripts.
- Avoid destructive default behavior in operational commands.

## Conventions

- Language: English in comments, docs, and change messages.
- Maintain compatibility with current deployment.
- Prefer safe defaults configurable through environment variables.

## Pull requests

Include in each PR:

- Functional summary.
- Risks and mitigations.
- Test evidence (CI output or manual verification).
