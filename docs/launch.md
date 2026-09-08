# Launch kit for git why

Everything below is drafted to post as-is. Replace the repo URL if the name changes.
Repo: https://github.com/maledadams/git-why

---

## Before you post

- [ ] Repo is public, README renders, `docs/demo.svg` shows on the page
- [ ] CI badge is green (push once, let Actions run)
- [ ] Topics added on GitHub: `git`, `cli`, `developer-tools`, `ai`, `agents`, `provenance`, `git-hooks`
- [ ] "About" blurb set to: *git blame tells you who. git why tells you why.*
- [ ] 5–7 issues created from `docs/good-first-issues.md`, labelled `good first issue`
- [ ] You've used it on one real repo of your own and can screenshot that

## Timing

- **Hacker News (Show HN):** Tuesday–Thursday, 8–10am US Eastern. Post, then don't touch it.
  Reply to every comment for the first 3–4 hours, plainly, no defensiveness.
- **Reddit:** same window or slightly later. One subreddit per day, not all at once.
- **Dev.to:** any weekday morning. Cross-link it from the HN thread only if someone asks "how does it work".

---

## Hacker News — "Show HN"

**Title:**
```
Show HN: git why – recover the reasoning behind a commit
```

**URL:** `https://github.com/maledadams/git-why`

**First comment (post immediately after submitting):**
```
I build a lot of things now by directing an AI, and I kept hitting the same
problem: the code gets committed, but the reasoning — why this approach, what
we rejected, what I actually asked for — stays in a chat window that closes.
A month later `git blame` tells me who and when, and nothing tells me why.

git why stores that reasoning as standard git trailers on the commit message
(Why:, Why-Rationale:, Why-Agent:, ...). Because they're trailers, they're in
the commit, they survive clone/push, and `git log` already shows them. No
database, no service.

It's one Python file, no dependencies. Commands:
  git why <commit|path>   show the reasoning
  git why log             the reasoning trail
  git why check <range>   CI gate, fails if a Why: is missing
  git why init            installs a commit-msg hook that enforces it

Writing is just `git commit --trailer "Why: ..."` under the hood; `git why
commit` is a shorter wrapper.

Limitations right now: long prompts have to fit in the commit message (git
notes fallback is planned), and there's no export/analysis command yet.

Would love feedback on the trailer schema in particular — whether the fields
are the right ones, and whether anyone would want this wired into their
agent setup.
```

Notes:
- Don't editorialise the title. "recover the reasoning behind a commit" is the whole pitch.
- If it doesn't catch the first time, it's fine to Show HN again in a few weeks with a real
  changelog ("added git notes support, export").

---

## Reddit — r/commandline

**Title:**
```
git why – a git subcommand that stores *why* a commit exists, as git trailers
```

**Body:**
```
`git blame` answers who and when. Nothing answers why — the reasoning usually
died in a chat log or a Slack thread.

git why writes the reasoning into the commit message as trailers (Why:,
Why-Rationale:, Why-Alternatives:, Why-Agent:, ...) and reads it back:

    $ git why HEAD
    commit a1b2c3d  ...
      why  Let users narrow cat results by breed
      | rationale  client-side filter on the already-fetched list
      | rejected   server-side query per breed — extra requests

    $ git why src/filter.ts     # reasoning for the last change to a file
    $ git why log               # the trail
    $ git why check main..HEAD  # CI: fail if a Why: is missing

One Python file, no dependencies. Writing is `git commit --trailer` under the
hood, so nothing proprietary ends up in your history.

MIT, feedback welcome: https://github.com/maledadams/git-why
```

---

## Reddit — r/git

**Title:**
```
Built a subcommand that puts commit reasoning in git trailers (git why)
```

**Body:**
```
I wanted the "why" of a change to live where the change lives. git trailers
seemed like the right primitive — they're already how Co-Authored-By and
Signed-off-by work, `git interpret-trailers` parses them, and they survive
clone/push for free.

git why is a thin layer on that:
- `git why <rev|path>` — pretty-print the Why:/Why-* trailers
- `git why log [range]` — timeline
- `git why check [range]` — non-zero exit if a commit has no Why:, for CI
- `git why init` — commit-msg hook enforcing it when why.strict is set

Deliberately not using git notes as the primary store because notes don't
push by default; notes are on the roadmap only as a fallback for oversized
prompts.

Curious what this sub thinks of the approach, and whether the trailer key
names are sensible: https://github.com/maledadams/git-why
```

---

## Reddit — r/programming

r/programming is link-only and heavily filtered; post the repo link with the
exact title:
```
git why – recover the reasoning behind a commit, stored as git trailers
```
Then leave a top comment with the same body as the r/commandline post.

---

## Dev.to / Medium article

**Title:** `I kept losing the "why" behind AI-written code, so I built git why`

**Tags:** `git`, `cli`, `ai`, `productivity`

**Body:**

```markdown
## The problem

I build a lot of software now by describing what I want to an AI agent and
reviewing what comes back. It works. But there's a hole in the workflow that
took me a while to name.

When a change lands, the commit records *what* changed and *who* committed it.
The *why* — why this approach and not the other one, what we tried first, what
I actually asked for — never makes it into the repo. It stays in a chat
transcript that I close and never open again.

Three months later I'm staring at a function, running `git blame`, and the
answer it gives me ("you, in April") is useless. The reasoning is gone.

## What I wanted

- The reasoning attached to the commit, not a separate system
- No service to run, no database to keep in sync
- Visible in tools I already use (`git log`)
- Survives a clone

## The primitive: git trailers

Git already has a place for structured metadata on a commit: **trailers**. They're
the `Key: value` lines at the bottom of a commit message — `Co-Authored-By:`,
`Signed-off-by:`, `Reviewed-by:`. Git ships `git interpret-trailers` to parse
them, and `git commit --trailer "Key: value"` to add them.

They're part of the commit message, so they're in the commit object. They push,
they clone, they show up in `git log` with zero configuration.

So the schema is just:

    Why: what this change is for
    Why-Prompt: the instruction that produced it
    Why-Rationale: why this approach
    Why-Alternatives: what was considered and rejected
    Why-Agent: model + tool that wrote it
    Why-Session: id grouping commits from one work session

## The tool

`git why` is one Python file with no dependencies. It reads those trailers back:

    $ git why HEAD
    commit a1b2c3d  2026-09-08 14:22  Lucia Adams
    Add breed filter to cat-finder

      why  Let users narrow cat results by breed
      | rationale  client-side filter on the already-fetched list
      | rejected   server-side query per breed — extra requests
      | agent      claude-sonnet-5

`git why <path>` shows the reasoning for the last commit that touched a file —
the `git blame` counterpart. `git why log` is the timeline. `git why check
main..HEAD` exits non-zero if any commit in the range has no `Why:`, so you can
enforce it in CI. `git why init` installs a `commit-msg` hook for local
enforcement.

Writing is `git commit --trailer` under the hood. `git why commit -m … -b …` is
just a shorter way to type it.

## Wiring it into an agent

One line in the agent's instructions:

> Commit with `git why commit -m "<subject>" -b "<why this change exists>"
> --prompt "<the request>" --agent "<model>"`. Never use bare `git commit`.

The hook catches it if the agent forgets.

## What it isn't

It's not a decision-tracking platform or a chat archive. It's a convention plus
a reader. If the reasoning doesn't fit in a commit message, that's a signal the
change is too big.

## Try it

    pipx install git+https://github.com/maledadams/git-why

Repo, MIT licensed: https://github.com/maledadams/git-why — feedback on the
trailer schema especially welcome.
```

---

## One-liners for wherever

- **GitHub About:** git blame tells you who. git why tells you why.
- **Twitter/Mastodon:** `git blame` tells you who wrote a line. `git why` tells you why it exists — reasoning stored as git trailers, so it's in the commit and shows in `git log`. One file, no deps. [link]
- **LinkedIn:** short version of the Dev.to intro + link.
