## What & why

Briefly describe the change and the motivation.

## Checklist

- [ ] `python -m py_compile scripts/*.py` passes
- [ ] `ruff check .` passes
- [ ] No secrets added (`.env` stays git-ignored; only placeholders in `.env.example`)
- [ ] Scripts remain standard-library only
- [ ] Tested with `hermes -p berghain cron run <job>` (if behavior changed)
