# Project map

```
cursor-agent/
├── bot.py                      # Telegram <-> Cursor Agent CLI bridge
├── stack.yml                   # Safe-by-default Docker/Portainer stack
├── stack.safe.yml              # Explicit safe profile
├── stack.ops.yml               # Ops profile with docker.sock and active commands
├── .env.example                # Minimum environment variables
├── README.md                   # Usage and security guide
├── CHANGELOG.md                # Change history
├── ROADMAP.md                  # Improvement plan
├── LICENSE                     # Project license
├── SECURITY.md                 # Security policy
├── CONTRIBUTING.md             # Contributor guide
├── CODE_OF_CONDUCT.md          # Code of conduct
├── .editorconfig               # Basic formatting rules
├── .gitignore                  # Exclusions for GitHub publishing
└── .github/workflows/ci.yml    # Minimal CI (compile + hygiene checks)
```

## Operational notes

- `home/` is used as a local runtime volume and must not be versioned.
- The project is ready for publishing, but secret rotation is required if previous exposure happened.
