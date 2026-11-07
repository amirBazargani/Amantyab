---
description: Phase gate. Run at the last task of each phase. Produces DB backup, tag and a checklist.
---
1. Open the phase's "Phase deliverables checklist" in `tasks/phase-<N>.md` and verify each line with evidence (file path, URL, command).
2. `python manage.py check`, `makemigrations --check --dry-run`, `migrate` on a fresh database (drop & recreate DB, then migrate) to prove migrations are clean.
3. Create the DB backup: `pg_dump --no-owner --no-privileges -U <user> -h <host> <dbname> > db_backup/phase-<N>.sql` (use the values from .env). Commit it: `chore: add database backup for phase <N>`.
4. Update `docs/REPORT.md` sections that this phase completes.
5. Tag: `git tag -a phase-<N>-done -m "Phase <N> delivered"` (push tag only after human approval).
6. Output a Persian summary: what is delivered, what is missing, and the "demo script" (5–8 steps the human can show the instructor).
