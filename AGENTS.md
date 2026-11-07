# AGENTS.md — Amanat-yab (امانت یاب)

Peer-to-peer neighbourhood tool/item rental platform ("هرچه نیاز داری همسایگی توست").
University web-programming final project. ONE human developer + you (the agent).
The human must be able to explain EVERY commit to an instructor. Work in small, explainable steps.

## Stack (fixed)
- Backend: Django (latest LTS-compatible), PostgreSQL ONLY (never SQLite), Pillow for images.
- Frontend: Django templates + Tailwind; React "islands" (Vite) added in Phase 4 (see docs/DECISIONS.md D-02).
- UI language: Persian, RTL. Code, identifiers, commit messages: English.

## Read order at the start of EVERY conversation
1. `docs/STATE.md`  (where we are)
2. `tasks/phase-<N>.md` → only the current task section
3. `docs/DOMAIN.md` (models) and `docs/DECISIONS.md` when the task touches them
Do not read the whole repo. Do not read other phases' tasks.

## Commands (workflows in .agent/workflows)
`/resume` → `/start-task <ID>` → (human approves plan) → `/implement` → `/verify` → `/commit` → `/explain` → `/finish-task`
End of phase: `/phase-review`.

## Non-negotiable rules
See `.agent/rules/` (project, git, code). Short version:
- One task at a time. Stay inside the task's "Files" list. Ask ONE question if blocked.
- Never push to `main` directly. Never force-push. Never rewrite published history.
- Never mark a task done without showing real output of `/verify`.
- Never add a package that is not in docs/DECISIONS.md without asking.
- Never invent features. The only extras allowed are those in docs/DECISIONS.md D-06: email + SMS notifications, map, React islands (P4-05). Still excluded: SMS-based account verification, Permission extras, Pagination, per-role dashboards other than admin, any other bonus item.
