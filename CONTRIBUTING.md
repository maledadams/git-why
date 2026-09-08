# Contributing to git why

Thanks for looking. This is a small project and that's on purpose — the whole tool
is one file, [`git_why.py`](git_why.py), Python 3.8+, no dependencies.

## Running it

```bash
python3 git_why.py --help          # run straight from source
sh test/smoke.sh                   # the full check: builds a throwaway repo end to end
```

`test/smoke.sh` is the test suite. It must print `SMOKE OK`. CI runs it on 3.8 and 3.12.

## Sending a change

1. Fork, branch, make the change.
2. Keep it in one file. If a change needs a second module, open an issue first so we
   can talk about scope.
3. Run `sh test/smoke.sh`. Add a few lines to it if you added behaviour.
4. Commit with `git why commit` — dogfooding is the point:
   ```bash
   python3 git_why.py commit -m "your subject" -b "why this change exists"
   ```
5. Open the PR. Describe what and why; the how is in the diff.

## Good first issues

Anything tagged [`good first issue`](https://github.com/maledadams/git-why/labels/good%20first%20issue)
is scoped to be self-contained and doesn't need deep git knowledge. If one is unclear,
comment on it and I'll add detail. No PR is too small.

## Scope

`git why` reads and writes commit-message trailers. It is not a decision-tracking
platform, a chat archive, or a code-review tool. Changes that keep it a sharp
single-purpose CLI are the ones that get merged fast.

## Conduct

Be kind. Assume good faith. That's the whole policy.
