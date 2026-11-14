# Amanat-yab (امانت یاب) — project + agent kit

## Install the kit (once, before P1-01)
1. Create an empty GitHub repo `amanatyab`, clone it locally.
2. Copy ALL contents of this kit into the repo root (keep the hidden `.agent/` folder).
3. `git add . && git commit -m "chore: add agent kit and project docs" && git push`
   (this is commit #1; it explains the project to the instructor too).
4. Open the repo folder in Antigravity. Workflows are the slash commands in `.agent/workflows/`; rules load from `.agent/rules/` and `AGENTS.md`.
5. In Antigravity settings set terminal command policy to "request review" (or equivalent) so `git push` always asks you.
6. Fill `repo_url` and deadlines in `docs/STATE.md`; email the repo link to the instructor.
7. New agent chat → type `/resume`, then `/start-task P1-01`.

## The loop for every task
`/start-task <ID>` → you approve the plan → `/implement` → `/verify` → `/commit` → `/explain` (answer the 3 questions) → `/finish-task` (you approve the push).
End of each phase: `/phase-review`.

## Folder map
- `AGENTS.md`, `.agent/` — agent instructions (rules + workflows)
- `docs/` — STATE, DOMAIN, PROCESSES, DECISIONS, COMMIT-LOG, DEFENSE, REPORT
- `tasks/phase-1..4.md` — every task with files, acceptance, commits
- `backend/`, `frontend/`, `db_backup/` — created by the agent during the tasks

## Scheduling Background Commands

### Rental Ending Reminder (`send_rental_reminders`)
The platform includes an automated reminder command to notify renters via email and SMS before their rental period expires:

```bash
# Run once with default hours (from RENTAL_REMINDER_HOURS in settings, default: 3):
python manage.py send_rental_reminders

# Run once checking up to 5 hours ahead:
python manage.py send_rental_reminders --hours 5

# Run continuously as a background daemon (polls every 60 seconds):
python manage.py send_rental_reminders --loop --interval 60
```

#### Linux / macOS (cron)
Add an entry to crontab (`crontab -e`) to run periodically (e.g. every 15 minutes):
```cron
*/15 * * * * cd /path/to/project/backend && /path/to/project/.venv/bin/python manage.py send_rental_reminders >> /path/to/project/logs/reminders.log 2>&1
```

#### Windows (Task Scheduler)
Create a scheduled task via Command Prompt or PowerShell:
```cmd
schtasks /create /tn "AmanatyabReminder" /tr "C:\path\to\project\.venv\Scripts\python.exe C:\path\to\project\backend\manage.py send_rental_reminders" /sc minute /mo 15
```
Or run as a persistent background service using the `--loop` flag:
```cmd
C:\path\to\project\.venv\Scripts\python.exe C:\path\to\project\backend\manage.py send_rental_reminders --loop --interval 60
```
