---
description: Run all checks for the current task and show real output. Never claim success without it.
---
Run, in order, from the backend directory with the virtualenv active, and paste the real output tail of each:
1. `python manage.py check`
2. `python manage.py makemigrations --check --dry-run`  (must say "No changes detected")
3. `python manage.py migrate`
4. From Phase 4 on: `python manage.py test`
5. Walk through every bullet of the task's "Acceptance" section. For each, state PASS/FAIL and HOW it was verified (command, URL visited, shell snippet). Use `python manage.py shell` or `runserver` when needed.
6. If anything FAILS: fix it (still within scope), re-run from step 1. If it fails twice, STOP and describe the problem in Persian.
7. End with the PASS/FAIL table and "برای ادامه: /commit".
