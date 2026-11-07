---
description: Teach the human what the task's commits do, then quiz them. For instructor Q&A preparation.
---
For the commits of the current task (`git log main..HEAD --oneline`, then `git show --stat` / `git show <hash>` as needed):
1. In simple Persian explain: what changed, why it exists in the project, which Django concept it uses (e.g. ForeignKey, ModelForm, QuerySet), and how data flows through it. Max 25 lines.
2. Point at the 2 most important lines of code and say what each does.
3. Ask 3 short questions an instructor could ask about this task. Wait for the human's answers; correct them kindly.
4. Add the 3 questions with short model answers to `docs/DEFENSE.md` under the current phase (do not commit yet).
