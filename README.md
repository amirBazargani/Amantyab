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
