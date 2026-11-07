---
description: Begin a task. Usage `/start-task P1-05`. Creates the branch and proposes a plan. No code yet.
---
1. Read `docs/STATE.md` and the section of the given task ID in `tasks/phase-<N>.md`. Read docs/DOMAIN.md if the task touches models.
2. Check the previous task is marked done in STATE.md. If not, STOP and tell the human.
3. `git checkout main` → `git status` must be clean (else STOP) → `git checkout -b p<N>/<ID>-<slug>`.
4. Write a plan in Persian as a numbered list: files to create/change (must match the task's "Files"), each step in one line, the planned commits (type(scope): subject), and any assumption.
5. List anything in the task that is ambiguous (max 1 question).
6. STOP. Wait for the human to answer "تایید" or give changes. Do not write code before approval.
