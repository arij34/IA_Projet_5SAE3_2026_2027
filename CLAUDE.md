# Claude Code Instructions

## Challenges Prompt Journal

- For every significant Challenges AI implementation, prompt iteration, or optimization experiment, update `../User+Project Modules/docs/journal-prompts-challenges.md` in the same task.
- Preserve the exact prompt submitted, provider/model when known, design rationale, generated result, evaluation, and concrete improvements. For Claude Code implementation prompts, record the actual prompt; never reconstruct it from memory.
- Append stable experiment IDs and prompt versions. Preserve prior versions; do not invent prompts, results, dates, tests, metrics, or improvements. Mark work pending or **Not evaluated yet** until supported by evidence.
- Record actual automated test outcomes separately from manual review, expectations, and untested assumptions. Include token, latency, cost, or quality measurements only when measured.
- Update experiment status only when verified. Do not create journal entries for trivial changes or unrelated work.
- Never include API keys, credentials, `.env` values, or private user data in the journal.

## Permanent Git Safety

- Never create commits or push to GitHub or any remote unless the user explicitly authorizes that specific exception. This includes `git commit`, `git push`, `git commit --amend`, and any other command that creates or publishes commits.
- Never merge, rebase, cherry-pick, or otherwise modify Git history.
- Never change branches unless the user explicitly authorizes it.
- Never discard, reset, overwrite, or clean existing uncommitted work. Do not run destructive commands such as `git reset --hard`, `git clean`, or forced checkout operations.
- Do not stage files with `git add` unless the user explicitly requests staging.
- Git status, branches, diffs, and logs may be inspected. File edits and tests may be performed as requested, but all changes must remain local and uncommitted.
- Before every significant development task, inspect the relevant repository's working-tree status and preserve existing changes; do not assume uncommitted files belong to you.
- If a task appears to require a commit, push, merge, rebase, cherry-pick, or branch change, stop and ask for explicit permission before doing it.