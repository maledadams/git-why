# git why

**`git blame` tells you _who_. `git why` tells you _why_.**

When you build software by directing an AI, the reasoning behind each change
lives in a chat window that closes. Six months later the code is still there and
the "why" is gone. `git why` keeps it — on the commit itself, as standard
[git trailers](https://git-scm.com/docs/git-interpret-trailers), so it travels
with every clone, fetch and push and shows up in plain `git log`.

```
$ git why HEAD
commit a1b2c3d  2026-09-08 14:22  Lucia Adams
Add breed filter to cat-finder

  why  Let users narrow cat results by breed
  | prompt    add a dropdown that filters the cat list by breed using the cat API
  | rationale client-side filter on the already-fetched list; breed list is tiny
  | rejected  server-side query per breed - extra requests, no combined filter
  | agent     claude-sonnet-5
  | session   cat-finder-filters
```

## Install

```bash
pipx install git+https://github.com/maledadams/git-why
```

or drop the single file on your `PATH`:

```bash
curl -o ~/.local/bin/git-why https://raw.githubusercontent.com/maledadams/git-why/main/git_why.py
chmod +x ~/.local/bin/git-why
```

Either way git picks it up as a subcommand: `git why`.

## Use

```bash
git why init                       # install the enforcement hook (once per repo)

git why commit -m "add breed filter" \
  -b "let users narrow cat results by breed" \
  --rationale "client-side filter on the already-fetched list" \
  --agent claude-sonnet-5 --session cat-finder-filters

git why HEAD                       # reasoning for a commit
git why src/filter.ts             # reasoning for the last change to a file
git why log --since "7 days ago"  # the reasoning trail
git why check origin/main..HEAD   # CI gate: fail if a Why: is missing
```

You never have to use `git why commit` — a plain
`git commit --trailer "Why: ..."` works too. The wrapper is just shorter.

## The schema

Reasoning is stored as trailers on the commit message. One `Why:` per commit;
the rest are optional.

| Trailer              | Meaning                                   |
| -------------------- | ----------------------------------------- |
| `Why:`               | what this change is for (required)        |
| `Why-Prompt:`        | the instruction that produced it          |
| `Why-Rationale:`     | why this approach                         |
| `Why-Alternatives:`  | what was considered and rejected          |
| `Why-Spec:`          | requirement / issue it satisfies          |
| `Why-Agent:`         | model + tool that wrote it                |
| `Why-Session:`       | id grouping commits from one work session |
| `Why-Confidence:`    | `low` / `medium` / `high` / `human-reviewed` |

`git why init` installs a `commit-msg` hook that rejects commits with no `Why:`
while `git config why.strict` is `true`. Turn it off with
`git config why.strict false`.

## For AI agents

Add one line to your agent's instructions:

> Commit with `git why commit -m "<subject>" -b "<why this change exists>"
> --prompt "<the request>" --agent "<model>"`. Never use bare `git commit`.

The `commit-msg` hook is the backstop if it forgets.

## Why not just keep the chat logs

Chat logs aren't attached to the code, aren't in the repo, don't survive a
clone, and nobody greps them. A trailer is one line, lives on the commit, and
`git log` already shows it.

## License

MIT
