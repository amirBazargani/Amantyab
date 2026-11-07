---
description: Implement the approved plan for the current task. Small steps, only in-scope files.
---
1. Re-read the task section (Goal, Files, Acceptance). The scope is exactly that.
2. Implement step by step following the approved plan. After each logical unit run `python manage.py check`.
3. If you need a file outside "Files", or a new package, STOP and ask.
4. If a model changed: `python manage.py makemigrations` and read the generated migration; make sure names/fields match docs/DOMAIN.md.
5. Do NOT commit in this workflow. Do NOT start the next task.
6. End with: list of changed files (one line each) and "برای ادامه: /verify".
