---
sitemap: false
---

# Ready-to-paste "good first issue" tickets

Create these as GitHub issues and add the `good first issue` label. Each is
self-contained and touches only `git_why.py` or `test/smoke.sh`.

---

### 1. `git why --version`

There's no way to print the version. Add a `--version` flag that prints
`git why 0.1.0` (read the number from `git_why.py`, keep one source of truth).
Add a line to `test/smoke.sh` asserting it prints something matching `\d+\.\d+`.

---

### 2. Show relative dates in `git why log`

`git why log` prints `2026-09-07`. Add `--relative` to print `3 days ago`
instead, matching `git log --relative-date`. Git can do the formatting for you
via `--date=relative` and `%ad` in the format string.

---

### 3. `git why log --json`

Add a `--json` flag to `git why log` that emits one JSON object per commit
(`commit`, `subject`, `date`, and each `why_*` field) instead of the text view.
Newline-delimited (one object per line). Add a smoke assertion that pipes it to
`python3 -m json.tool`.

---

### 4. `--oneline` for `git why log`

One line per commit, no rationale/meta block: `<short>  <date>  <why>`. Useful
for skimming long histories. Small branch in `cmd_log`.

---

### 5. Respect `core.pager` / add `--no-pager`

Long `git why log` output should page like `git log` does when stdout is a TTY.
Pipe through `$GIT_PAGER` or `core.pager`, with `--no-pager` to opt out.

---

### 6. Friendlier error when git is too old

`git why commit` relies on `git commit --trailer` (git 2.32+). On older git it
fails with a confusing message. Detect the git version once and print a clear
"git why needs git 2.32 or newer" instead.

---

### 7. `git why blame <file>`

Like `git blame` but the last column is the `Why:` of each line's commit instead
of the author. Wrap `git blame --porcelain`, look up the trailer per commit
(cache by SHA), print `<short>  <why first 50 chars>  <line>`.
