---
description: Create atomic Conventional Commits for the current task after a passing /verify.
---
1. Refuse if the last /verify was not fully PASS.
2. `git status` and `git diff --stat`. Check that no secret, log, media, or `.env` file is included.
3. Split the work into 1–4 atomic commits following the plan (models+migration together; templates with their view; docs separate).
4. For each: `git add <specific files>` (never `git add .` blindly), `git commit -m "<type>(<scope>): <subject>" -m "<why, 1–2 lines>"`.
5. After each commit run `git log -1 --stat --format="%h %s"` and remember the hash.
6. Append one entry per commit to `docs/COMMIT-LOG.md` using its template (Persian explanation). Do NOT commit that file now; /finish-task does.
7. End with the list of hashes + subjects and "برای ادامه: /explain".
