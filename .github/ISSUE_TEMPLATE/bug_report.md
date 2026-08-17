---
name: Bug report
about: Something isn't working (missing digest, formatting, delivery)
title: ""
labels: bug
---

**What happened**
A clear description of the problem.

**Expected**
What you expected instead.

**Which job**
- [ ] `bh_daily`
- [ ] `bh_weekly`

**Steps / logs**
Output of a manual run helps a lot:

```
hermes -p berghain cron run <job>
```

Paste any relevant lines (redact your token/chat id).

**Environment**
- OS:
- Hermes version (`hermes --version`):
- Scheduler: gateway / launchd / other
