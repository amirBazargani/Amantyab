---
description: Close the task: update state files, merge to main, push after human approval.
---
1. Tick the task in `tasks/phase-<N>.md` (`- [x]`) and fill its "Done notes" (what was done, manual QA performed, deviations).
2. Update `docs/STATE.md`: last_completed, current_task = next task ID, date, notes for next session (max 5 lines).
3. Commit docs only: `git add docs tasks` → `git commit -m "docs: update state, commit log and defense notes for <ID>"`.
4. `git checkout main && git merge --no-ff p<N>/<ID>-<slug> -m "Merge <ID>: <task title>"`.
5. Show `git log --oneline --graph -8`.
6. Ask the human: "push کنم؟" — only after "بله": `git push origin main` and `git push origin p<N>/<ID>-<slug>`.
7. End with: next task ID and "برای ادامه: /start-task <next ID>".
