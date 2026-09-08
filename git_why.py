#!/usr/bin/env python3
"""git why - recover the reasoning behind a commit.

Put the "why" in version control.

Reasoning lives in git trailers on the commit message (Why:, Why-Prompt:,
Why-Rationale: ...), so it travels with every clone, fetch and push and shows
up in plain `git log`. This tool writes those trailers, reads them back as a
timeline, exports them, and (optionally) enforces them - but only where the
change is big enough to deserve a reason.
"""
import argparse
import json
import os
import re
import stat
import subprocess
import sys
from fnmatch import fnmatch

__version__ = "0.1.0"  # single source of truth; keep in sync with pyproject.toml

KEYS = ["Why", "Why-Prompt", "Why-Rationale", "Why-Alternatives",
        "Why-Spec", "Why-Agent", "Why-Session", "Why-Confidence"]
LABEL = {"Why-Prompt": "prompt", "Why-Rationale": "rationale",
         "Why-Alternatives": "rejected", "Why-Spec": "spec",
         "Why-Agent": "agent", "Why-Session": "session",
         "Why-Confidence": "confidence"}

US, FS = "\x1f", "\x1e"
SUBCOMMANDS = {"log", "check", "check-msg", "export", "init", "commit", "agent-setup"}

# Changes this small (or matching these) don't need a recorded reason.
SKIP_GLOBS = ["*.lock", "*-lock.json", "*-lock.yaml", "*-lock.yml",
              "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "go.sum",
              "Cargo.lock", "poetry.lock", "composer.lock", "Gemfile.lock",
              "*.min.js", "*.min.css", "*.snap"]
SKIP_SUBJECT_RE = re.compile(r"^(chore|build|ci|deps|revert|release|bump)(\(|:|\b)"
                             r"|^(merge|revert) ", re.I)
# Filler that is not a reason.
BANNED_WHY = {"update", "updates", "updated", "fix", "fixes", "fixed", "fix bug",
              "changes", "change", "changed", "wip", "stuff", "misc", "cleanup",
              "clean up", "refactor", "tweaks", "tweak", "minor changes",
              "minor fixes", "various", "done", "initial commit", "commit"}

HOOK_BEGIN = "# >>> git-why commit-msg check >>>"
HOOK_END = "# <<< git-why commit-msg check <<<"
HOOK_FRAGMENT = f"""{HOOK_BEGIN}
if command -v git-why >/dev/null 2>&1; then
  git why check-msg "$1" || exit 1
else
  # fallback if git-why is not on PATH: enforce only when why.strict is "all"
  if [ "$(git config --get why.strict 2>/dev/null)" = "all" ]; then
    git interpret-trailers --parse <"$1" | grep -qiE '^Why:' || {{
      echo "git-why: commit blocked - no 'Why:' trailer." >&2; exit 1; }}
  fi
fi
{HOOK_END}
"""

AGENT_BLOCK = """\
# git-why

When you make a commit, record why the change exists:

    git why commit -m "<subject>" -b "<the reason this change exists>" \\
      --prompt "<the request that led to it>" --agent "<your model id>"

Write the reason yourself, inferred from what the user is trying to achieve in
the conversation - the point is to capture intent the user never has to type.
Only ask them for it if their intent is genuinely ambiguous.

By default git-why never blocks a commit - it just prints a one-line tip if a
non-trivial change has no reason. Still record one on anything that isn't
trivial; a lockfile bump, a typo or a formatting-only change needs nothing.
"""


def git(*args, check=True):
    r = subprocess.run(["git", *args], text=True, capture_output=True)
    if check and r.returncode != 0:
        sys.stderr.write(r.stderr or f"git {' '.join(args)}: failed\n")
        sys.exit(r.returncode or 1)
    return r.stdout


def git_ok(*args):
    return subprocess.run(["git", *args], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode == 0


def cfg(key, default=None):
    v = git("config", "--get", f"why.{key}", check=False).strip()
    return v or default


def paint(s, code, bold=False):
    if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        return s
    c = {"dim": "2", "red": "31", "green": "32", "yellow": "33", "cyan": "36"}[code]
    return f"\033[{'1;' if bold else ''}{c}m{s}\033[0m"


def norm(s):
    return re.sub(r"[\s\W_]+", " ", (s or "").strip().lower()).strip()


def parse_trailers(block):
    """`Key: value` lines (already unfolded) -> [(key, value), ...], Why* only."""
    out = []
    for line in block.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip()
        if k == "Why" or k.startswith("Why-"):
            out.append((k, v.strip()))
    return out


def trailers_of_msg_file(path):
    """Parse trailers from a raw commit-message file (handles folded lines)."""
    return parse_trailers(git("interpret-trailers", "--parse", path, check=False))


def log_records(rev_args):
    fmt = US.join(["%H", "%h", "%cI", "%an", "%P", "%s", "%(trailers:unfold,only)"])
    out = git("log", f"--format={fmt}{FS}", *rev_args)
    for chunk in out.split(FS):
        if not chunk.strip():
            continue
        p = (chunk.strip("\n").split(US, 6) + [""] * 7)[:7]
        yield {"full": p[0], "short": p[1], "date": p[2][:10], "time": p[2][11:16],
               "author": p[3], "parents": p[4].split(), "subject": p[5],
               "trailers": parse_trailers(p[6])}


def first_of_each(trailers):
    d, order = {}, []
    for k, v in trailers:
        if k not in d:
            order.append(k)
        d.setdefault(k, v)
    return d, order


# --- "does this change deserve a reason" ----------------------------------- #

def _skip_path(path):
    base = os.path.basename(path)
    globs = SKIP_GLOBS + [g.strip() for g in (cfg("skip-paths", "") or "").split(",") if g.strip()]
    return any(fnmatch(path, g) or fnmatch(base, g) for g in globs)


def _size_from_numstat(text):
    lines = files = 0
    for row in text.splitlines():
        parts = row.split("\t")
        if len(parts) != 3:
            continue
        a, d, path = parts
        if _skip_path(path.strip()):
            continue
        files += 1
        lines += (int(a) if a.isdigit() else 0) + (int(d) if d.isdigit() else 0)
    return lines, files


def is_substantial(subject, numstat_text):
    if SKIP_SUBJECT_RE.search(subject or ""):
        return False
    lines, files = _size_from_numstat(numstat_text)
    return lines >= int(cfg("threshold", "15") or "15")


def why_quality_problem(why, subject):
    n = norm(why)
    if len(n) < 12:
        return "is too short to be a reason"
    if n in BANNED_WHY:
        return "is filler, not a reason"
    if n == norm(subject):
        return "just repeats the commit subject"
    return None


def enforcement_level():
    """off | nudge (default, never blocks) | substantial | all."""
    v = (cfg("strict", "nudge") or "nudge").lower()
    return {"true": "all", "false": "off", "no": "off", "0": "off", "yes": "all",
            "1": "all", "": "nudge", "on": "substantial", "tip": "nudge"}.get(v, v)


# --------------------------------------------------------------------------- #

def cmd_show(target):
    if target in ("-h", "--help"):
        print(__doc__)
        print("usage: git why [<commit> | <path>]        show the reasoning")
        print("       git why log [<range>] [filters]    timeline of reasoning")
        print("       git why commit -m MSG -b WHY ...   commit with a Why: trailer")
        print("       git why check [<range>]            CI: fail if a reason is missing")
        print("       git why export [<range>]           NDJSON of every reason recorded")
        print("       git why init [--all|--no-strict]   install the enforcement hook")
        print("       git why agent-setup                print instructions for an AI agent")
        return 0
    target = target or "HEAD"
    if git_ok("rev-parse", "--verify", "--quiet", f"{target}^{{commit}}"):
        rev = target
    else:
        if not os.path.exists(target) and not git_ok("ls-files", "--error-unmatch", target):
            sys.stderr.write(f"git why: '{target}' is not a commit or a tracked path\n")
            return 2
        rev = git("log", "-1", "--format=%H", "--", target).strip()
        if not rev:
            sys.stderr.write(f"git why: no commit touches '{target}'\n")
            return 1
        print(paint(f"last change to {target}", "dim"))
    rec = next(log_records(["-1", rev]))
    tr, order = first_of_each(rec["trailers"])
    print(f"{paint('commit ' + rec['short'], 'yellow')}  {rec['date']} {rec['time']}  {rec['author']}")
    print(rec["subject"])
    print()
    if "Why" not in tr:
        print("  " + paint("no reason recorded", "red"))
        print("  " + paint('add it:  git commit --amend --trailer "Why: ..."', "dim"))
        return 0
    print("  " + paint("why", "green", bold=True) + "  " + tr["Why"])
    for k in KEYS[1:] + [k for k in order if k not in KEYS]:
        if k in tr and k != "Why":
            print("  " + paint("| " + LABEL.get(k, k[4:].lower()).ljust(9), "dim") + " " + tr[k])
    return 0


def cmd_log(args):
    rev_args = list(args.range)
    if args.since:
        rev_args = ["--since", args.since, *rev_args]
    first = True
    for rec in log_records(rev_args):
        tr, _ = first_of_each(rec["trailers"])
        if args.agent and args.agent.lower() not in tr.get("Why-Agent", "").lower():
            continue
        if args.session and args.session.lower() not in tr.get("Why-Session", "").lower():
            continue
        if args.spec and args.spec.lower() not in tr.get("Why-Spec", "").lower():
            continue
        if args.with_reason and "Why" not in tr:
            continue
        if not first:
            print()
        first = False
        why = tr.get("Why") or paint("(no reason recorded)", "red")
        print(f"{paint(rec['short'], 'yellow')}  {rec['date']}  {why}")
        if tr.get("Why-Rationale"):
            print("          " + paint("rationale: " + tr["Why-Rationale"], "dim"))
        meta = [f"{LABEL[k]}: {tr[k]}" for k in ("Why-Agent", "Why-Session", "Why-Spec") if tr.get(k)]
        if meta:
            print("          " + paint("   ".join(meta), "dim"))
    if first:
        print("no matching commits")
    return 0


def cmd_export(args):
    n = 0
    for rec in log_records(args.range):
        tr, _ = first_of_each(rec["trailers"])
        if "Why" not in tr and not args.all:
            continue
        obj = {"commit": rec["full"], "short": rec["short"], "date": rec["date"],
               "author": rec["author"], "subject": rec["subject"]}
        for k, v in tr.items():
            key = "why" if k == "Why" else "why_" + k[4:].lower().replace("-", "_")
            obj[key] = v
        print(json.dumps(obj, ensure_ascii=False))
        n += 1
    if n == 0:
        sys.stderr.write("git why: no records to export\n")
    return 0


def cmd_check(args):
    if args.range:
        rng = list(args.range)
    elif git_ok("rev-parse", "--verify", "--quiet", "@{upstream}"):
        rng = ["@{upstream}..HEAD"]
    else:
        rng = ["-1", "HEAD"]
    level = args.level or enforcement_level()
    if level in ("off", "nudge"):
        print(f"git why check: why.strict is '{level}' - not a CI gate. "
              "pass --level substantial to check anyway.")
        return 0
    bad, checked = [], 0
    for rec in log_records(rng):
        if len(rec["parents"]) > 1:
            continue
        checked += 1
        numstat = git("show", "--numstat", "--format=", rec["full"], check=False)
        required = level == "all" or is_substantial(rec["subject"], numstat)
        tr, _ = first_of_each(rec["trailers"])
        if "Why-Skip" in tr:
            continue
        why = tr.get("Why", "")
        if not why:
            if required:
                bad.append((rec, "no reason recorded"))
            continue
        problem = why_quality_problem(why, rec["subject"])
        if problem and required:
            bad.append((rec, f"reason {problem}"))
    if bad:
        sys.stderr.write(paint(f"x {len(bad)}/{checked} commit(s) need a better reason\n", "red"))
        for rec, msg in bad:
            sys.stderr.write(f"  {rec['short']}  {msg}\n            {rec['subject']}\n")
        return 1
    print(paint(f"ok - {checked} commit(s) checked ({level})", "green"))
    return 0


def cmd_check_msg(args):
    """Called by the commit-msg hook with the message file path."""
    path = args.file
    level = enforcement_level()
    if level == "off" or os.environ.get("GIT_WHY_SKIP"):
        return 0
    if git_ok("rev-parse", "--verify", "--quiet", "MERGE_HEAD"):
        return 0
    try:
        raw = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return 0
    subject = next((l for l in raw.splitlines() if l.strip() and not l.startswith("#")), "")
    tr, _ = first_of_each(trailers_of_msg_file(path))
    if "Why-Skip" in tr:
        return 0
    numstat = git("diff", "--cached", "--numstat", check=False)  # ponytail: approx for --amend
    lines, _files = _size_from_numstat(numstat)
    substantial = level == "all" or is_substantial(subject, numstat)
    why = tr.get("Why", "")
    problem = why_quality_problem(why, subject) if why else None

    if why and problem is None:      # a real reason is recorded - always fine
        return 0
    if not substantial:              # trivial change - never nag, whatever the level
        return 0

    if level == "nudge":             # default: let it through, leave a tip
        sys.stderr.write("\n".join([
            "",
            f"git-why: no reason recorded for this ~{lines}-line change (allowed through).",
            '  add one:  git commit --amend --trailer "Why: <why this change exists>"',
            "  quiet:    git config why.strict off",
            "", ""]))
        return 0

    # level is 'substantial' or 'all' - block
    if not why:
        head = "git-why: substantial change with no 'Why:' trailer."
    else:
        head = f"git-why: the 'Why:' trailer {problem}.\n  got:  {why}"
    sys.stderr.write("\n".join([
        "", head,
        '  add one:  git why commit -m "..." -b "<why this change exists>"',
        '  skip one: git commit --trailer "Why-Skip: <reason it needs none>"',
        "  relax:    git config why.strict nudge   (tip only, never blocks)",
        "", ""]))
    return 1


def cmd_commit(args):
    pairs = [("Why", args.because), ("Why-Prompt", args.prompt),
             ("Why-Rationale", args.rationale), ("Why-Alternatives", args.alternatives),
             ("Why-Spec", args.spec), ("Why-Skip", args.skip),
             ("Why-Agent", args.agent or cfg("agent", "")),
             ("Why-Session", args.session or os.environ.get("GIT_WHY_SESSION", "")),
             ("Why-Confidence", args.confidence)]
    trailers = []
    for k, v in pairs:
        if v:
            trailers += ["--trailer", f"{k}: {v}"]
    passthrough = args.git_args[1:] if args.git_args[:1] == ["--"] else args.git_args
    cmd = ["git", "commit", *trailers, *passthrough]
    if args.message is not None:
        cmd += ["-m", args.message]
    os.execvp("git", cmd)


def cmd_agent_setup(args):
    sys.stdout.write(AGENT_BLOCK)
    return 0


def cmd_init(args):
    hooks = os.path.join(git("rev-parse", "--git-dir").strip(), "hooks")
    os.makedirs(hooks, exist_ok=True)
    path = os.path.join(hooks, "commit-msg")
    if os.path.exists(path):
        cur = open(path).read()
        if HOOK_BEGIN in cur:
            new = re.sub(re.escape(HOOK_BEGIN) + r".*?" + re.escape(HOOK_END),
                         HOOK_FRAGMENT.strip(), cur, flags=re.S)
            open(path, "w").write(new)
            print("updated git-why block in existing commit-msg hook")
        else:
            with open(path, "a") as f:
                f.write("\n" + HOOK_FRAGMENT)
            print("appended git-why check to existing commit-msg hook")
    else:
        open(path, "w").write("#!/bin/sh\n" + HOOK_FRAGMENT)
        print(f"installed {path}")
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    level = ("all" if args.all else "substantial" if args.enforce
             else "off" if args.silent else "nudge")
    git("config", "why.strict", level)
    blurb = {"nudge": "one-line tip on a substantial reasonless commit, never blocks",
             "substantial": "blocks a substantial commit with no / weak reason",
             "all": "blocks every non-merge commit with no / weak reason",
             "off": "silent"}[level]
    print(f"why.strict = {level}   ({blurb})")
    if args.agent:
        git("config", "why.agent", args.agent)
        print(f"why.agent = {args.agent}")
    return 0


def main():
    argv = sys.argv[1:]
    if argv and argv[0] in ("-V", "--version"):
        print(f"git why {__version__}")
        return 0
    if not argv or argv[0] not in SUBCOMMANDS:
        if argv and argv[0] in ("-h", "--help"):
            return cmd_show("-h")
        return cmd_show(argv[0] if argv else None)

    p = argparse.ArgumentParser(prog="git why", add_help=True)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("log", help="timeline of recorded reasoning")
    sp.add_argument("range", nargs="*")
    sp.add_argument("--since", help="passed through to git log")
    sp.add_argument("--agent", help="only commits whose Why-Agent contains this")
    sp.add_argument("--session", help="only commits whose Why-Session contains this")
    sp.add_argument("--spec", help="only commits whose Why-Spec contains this")
    sp.add_argument("--with-reason", action="store_true", help="hide commits with no Why:")
    sp.set_defaults(fn=cmd_log)

    sp = sub.add_parser("export", help="NDJSON of every recorded reason")
    sp.add_argument("range", nargs="*")
    sp.add_argument("--all", action="store_true", help="include commits with no Why:")
    sp.set_defaults(fn=cmd_export)

    sp = sub.add_parser("check", help="fail if a commit that needs a reason lacks one")
    sp.add_argument("range", nargs="*")
    sp.add_argument("--level", choices=["off", "nudge", "substantial", "all"],
                    help="override why.strict for this run")
    sp.set_defaults(fn=cmd_check)

    sp = sub.add_parser("check-msg", help=argparse.SUPPRESS)
    sp.add_argument("file")
    sp.set_defaults(fn=cmd_check_msg)

    sp = sub.add_parser("init", help="install the commit-msg hook (tip-only by default)")
    g = sp.add_mutually_exclusive_group()
    g.add_argument("--enforce", action="store_true",
                   help="block substantial commits that have no / a weak reason")
    g.add_argument("--all", action="store_true",
                   help="block every non-merge commit that has no / a weak reason")
    g.add_argument("--silent", action="store_true", help="install the hook but stay quiet")
    sp.add_argument("--agent", help="set why.agent (stamped on every git why commit)")
    sp.set_defaults(fn=cmd_init)

    sp = sub.add_parser("commit", help="git commit + a Why: trailer")
    sp.add_argument("-m", "--message")
    sp.add_argument("-b", "--because", help="the Why: line (why this change exists)")
    sp.add_argument("--prompt", help="the instruction that produced the change")
    sp.add_argument("--rationale", help="why this approach")
    sp.add_argument("--alternatives", help="what was considered and rejected")
    sp.add_argument("--spec", help="requirement / issue this satisfies")
    sp.add_argument("--skip", metavar="REASON",
                    help="record Why-Skip: instead of Why: (change needs no reason)")
    sp.add_argument("--agent")
    sp.add_argument("--session")
    sp.add_argument("--confidence", choices=["low", "medium", "high", "human-reviewed"])
    sp.add_argument("git_args", nargs=argparse.REMAINDER,
                    help="args after -- go straight to git commit")
    sp.set_defaults(fn=cmd_commit)

    sp = sub.add_parser("agent-setup", help="print instructions to paste into an AI agent")
    sp.set_defaults(fn=cmd_agent_setup)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main() or 0)
