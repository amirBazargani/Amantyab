---
description: Apply a kit update file from updates/ (usage `/apply-update UPDATE-01`). Edits docs and tasks only, never code, never your progress.
---
1. Read `updates/<name>.md` completely. Read `docs/STATE.md`. `git status` must be clean (else STOP). `git checkout main` then `git checkout -b chore/<name>-kit-update`.
2. Apply every numbered section of the update file in order, using the stated anchors.
3. Hard rules while editing:
   - NEVER untick a ticked task, NEVER edit any "Done notes", NEVER renumber or rename an existing task ID.
   - New tasks are inserted as UNCHECKED blocks at the stated anchor (match anchors by the task title text, ignoring `[ ]`/`[x]`).
   - STATE.md: only append one line to "notes for next session"; change `current_task` only as section 8 says.
   - COMMIT-LOG.md and DEFENSE.md are not touched.
   - If an anchor text no longer exists, insert at the nearest logical place and tell the human.
4. Do not write or change any application code in this workflow.
5. Show `git diff --stat` and a Persian summary: files changed, new tasks (IDs + titles), and which new tasks are "catch-up" (they sit before already-finished work, so they must be done next).
6. Commit: `docs: apply kit update 01 (notifications, SMS, maps)`. Merge to main with `--no-ff`. Ask the human before any push.
