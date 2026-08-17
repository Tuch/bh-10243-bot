# Contributing

Thanks for taking a look! This is a small, single-purpose bot, so contributions
are simple.

## Ground rules

- **Never commit secrets.** The bot token and chat id live only in the profile's
  `.env` (git-ignored). `.env.example` holds placeholders — keep it that way.
- Keep the scripts **dependency-free** (Python standard library only). They run
  under whatever interpreter the Hermes cron scheduler provides, with no `pip`
  install step.
- Be gentle with Reddit: it rate-limits hard. Preserve the request spacing
  (`GAP_SECONDS`) and the 429 retry/backoff in `berghain_common.py`.

## Local checks

CI runs these on every push and pull request — run them before you push:

```bash
python -m py_compile scripts/*.py     # syntax
ruff check .                          # lint (config in ruff.toml)
```

## Making a change

- Edit shared logic in `scripts/berghain_common.py`; the two entry scripts
  (`berghain-daily.py`, `berghain-weekly.py`) just call `run(mode)`.
- Test a job end-to-end without waiting for the schedule:
  ```bash
  hermes -p berghain cron run bh_daily
  ```
- Open a PR against `main`. Keep commits focused and the diff minimal.
