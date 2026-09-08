<h1 align="center">git why</h1>

<p align="center">
  <strong><code>git blame</code> tells you <em>who</em>. <code>git why</code> tells you <em>why</em>.</strong>
</p>

<p align="center">
  <a href="https://github.com/maledadams/git-why/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/maledadams/git-why/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="License" src="https://img.shields.io/badge/license-MIT-blue.svg">
  <img alt="Dependencies" src="https://img.shields.io/badge/dependencies-0-brightgreen">
  <img alt="Single file" src="https://img.shields.io/badge/code-1%20file-blue">
  <img alt="Python" src="https://img.shields.io/badge/python-3.8%2B-blue">
</p>

When you build software by directing an AI, the reasoning behind each change lives in a
chat window that closes. Six months later the code is still there and the *why* is gone.
`git why` keeps it — on the commit itself, as standard
[git trailers](https://git-scm.com/docs/git-interpret-trailers), so it travels with every
clone, fetch and push and shows up in plain `git log`.

<p align="center">
  <img src="docs/demo.svg" alt="git why HEAD showing the reasoning behind a commit" width="760">
</p>

## Install

```bash
pipx install git+https://github.com/maledadams/git-why
```

or drop the single file on your `PATH` — no build, no dependencies:

```bash
curl -fsSL https://raw.githubusercontent.com/maledadams/git-why/main/git_why.py -o ~/.local/bin/git-why
chmod +x ~/.local/bin/git-why
```

Git picks it up as a subcommand automatically: `git why`.

## Quickstart

```bash
git why init                        # install the enforcement hook (once per repo)

git why commit -m "add breed filter" \
  -b "let users narrow cat results by breed" \
  --rationale "client-side filter on the already-fetched list" \
  --agent claude-sonnet-5

git why HEAD                        # reasoning for a commit
git why src/filter.ts              # reasoning for the last change to a file
git why log --since "7 days ago"   # the reasoning trail
git why check origin/main..HEAD    # CI gate: fail if a Why: is missing
```

You never *have* to use `git why commit` — a plain `git commit --trailer "Why: ..."` works
the same. The wrapper is just shorter.

## What gets stored

Reasoning is stored as trailers on the commit message. One `Why:` per commit; the rest are
optional.

| Trailer             | Meaning                                        |
| ------------------- | ---------------------------------------------- |
| `Why:`              | what this change is for **(required)**         |
| `Why-Prompt:`       | the instruction that produced it               |
| `Why-Rationale:`    | why this approach                              |
| `Why-Alternatives:` | what was considered and rejected               |
| `Why-Spec:`         | requirement / issue it satisfies               |
| `Why-Agent:`        | model + tool that wrote it                     |
| `Why-Session:`      | id grouping commits from one work session      |
| `Why-Confidence:`   | `low` / `medium` / `high` / `human-reviewed`   |

## How it works

- **Trailers, not a database.** Everything lives in the commit message's last paragraph,
  the same place as `Co-Authored-By:`. Nothing to host, nothing to sync.
- **`git why init`** installs a `commit-msg` hook that rejects commits with no `Why:` while
  `git config why.strict` is `true`. Turn it off any time with `git config why.strict false`.
- **`git why check`** is the same rule for CI — run it on a PR range and it exits non-zero
  if any commit is missing its reasoning.

## For AI agents

Add one line to your agent's instructions:

> Commit with `git why commit -m "<subject>" -b "<why this change exists>" --prompt "<the request>" --agent "<model>"`. Never use bare `git commit`.

The `commit-msg` hook is the backstop if it forgets.

## Why not just keep the chat logs

Chat logs aren't attached to the code, aren't in the repo, don't survive a clone, and
nobody greps them. A trailer is one line, lives on the commit, and `git log` already
shows it.

## Roadmap

v1 is deliberately small. Planned next, roughly in order:

- `git why export` — dump every record to NDJSON for analysis
- git notes fallback for prompts too long to sit in a message
- `--session` / `--spec` filters on `git why log`
- an editor-time staging file so an agent can record intent before it commits
- editor integrations (VS Code, Neovim) surfacing `git why` on the current line

## Contributing

Issues and PRs are welcome, including from first-timers — see
[CONTRIBUTING.md](CONTRIBUTING.md) and the
[`good first issue`](https://github.com/maledadams/git-why/labels/good%20first%20issue) label.

## License

MIT © Lucia Adams
