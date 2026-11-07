# Git rules
- Branch per task from up-to-date `main`: `p<phase>/<TASK-ID>-<slug>`, e.g. `p1/P1-05-catalog-models`.
- Commits: Conventional Commits, English, imperative, <= 72 chars subject.
  types: feat, fix, docs, test, refactor, chore, perf. scope = app name. Example: `feat(catalog): add Item and Category models`
- Atomic commits: 1–4 per task. Each commit must leave the project runnable (`manage.py check` passes).
- Commit body (when non-trivial): WHY the change exists, one or two lines.
- Never commit: `.env`, `logs/*.log`, `media/`, `__pycache__`, `node_modules`, `venv`.
- Migrations are committed together with the model change that created them.
- After a task: merge into `main` with `git merge --no-ff <branch>` so the history shows one merge per task. Then ask the human to confirm before `git push origin main` (and the branch).
- Tag at phase end: `phase-<N>-done`.
- The terminal may run git commands, but `git push` always waits for human approval.
