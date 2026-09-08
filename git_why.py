#!/usr/bin/env python3
"""git why - recover the reasoning behind a commit.

git blame tells you who. git why tells you why.

Reasoning lives in git trailers on the commit message (Why:, Why-Prompt:,
Why-Rationale:, ...), so it travels with every clone, fetch and push and
shows up in plain `git log`. This tool writes those trailers and reads
them back as a timeline.
"""
import argparse
import os
import re
import stat
import subprocess
import sys

# Canonical trailer keys, in display order. Any other "Why-*" key is still
# read and shown, just after these.
KEYS = ["Why", "Why-Prompt", "Why-Rationale", "Why-Alternatives",
        "Why-Spec", "Why-Agent", "Why-Session", "Why-Confidence"]
LABEL = {"Why-Prompt": "prompt", "Why-Rationale": "rationale",
         "Why-Alternatives": "rejected", "Why-Spec": "spec",
         "Why-Agent": "agent", "Why-Session": "session",
         "Why-Confidence": "confidence"}

US, FS = "\x1f", "\x1e"  # field / record separators for `git log --format`
SUBCOMMANDS = {"log", "check", "init", "commit"}

HOOK_BEGIN = "# >>> git-why commit-msg check >>>"
HOOK_END = "# <<< git-why commit-msg check <<<"
HOOK_FRAGMENT = f"""{HOOK_BEGIN}
# Reject commits with no "Why:" trailer while why.strict is set.
if [ "$(git config --bool --get why.strict)" = "true" ]; then
  if ! git interpret-trailers --parse <"$1" | grep -qiE '^Why:'; then
    echo "git-why: commit blocked - no 'Why:' trailer." >&2
    echo "  add one:  git why commit -m \\"...\\" -b \\"<reason this change exists>\\"" >&2
    echo "  or:       git commit --trailer \\"Why: <reason>\\"" >&2
    echo "  bypass:   git config why.strict false" >&2
    exit 1
  fi
fi
{HOOK_END}
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


def paint(s, code, bold=False):
    if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        return s
    c = {"dim": "2", "red": "31", "green": "32", "yellow": "33", "cyan": "36"}[code]
    return f"\033[{'1;' if bold else ''}{c}m{s}\033[0m"


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


def log_records(rev_args):
    fmt = US.join(["%H", "%h", "%cI", "%an", "%s", "%(trailers:unfold,only)"])
    out = git("log", f"--format={fmt}{FS}", *rev_args)
    for chunk in out.split(FS):
        if not chunk.strip():
            continue
        p = (chunk.strip("\n").split(US, 5) + [""] * 6)[:6]
        yield {"full": p[0], "short": p[1], "date": p[2][:10], "time": p[2][11:16],
               "author": p[3], "subject": p[4], "trailers": parse_trailers(p[5])}


def first_of_each(trailers):
    d, order = {}, []
    for k, v in trailers:
        if k not in d:
            order.append(k)
        d.setdefault(k, v)
    return d, order


# --------------------------------------------------------------------------- #

def cmd_show(target):
    if target in ("-h", "--help"):
        print(__doc__)
        print("usage: git why [<commit> | <path>]        show the reasoning")
        print("       git why log [<range>]              timeline of reasoning")
        print("       git why commit -m MSG -b WHY ...   commit with a Why: trailer")
        print("       git why check [<range>]            CI: fail if a Why: is missing")
        print("       git why init [--no-strict]         install the enforcement hook")
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
        print("  " + paint("no why recorded", "red"))
        print("  " + paint('add it:  git commit --amend --trailer "Why: ..."', "dim"))
        return 0
    print("  " + paint("why", "green", bold=True) + "  " + tr["Why"])
    for k in KEYS[1:] + [k for k in order if k not in KEYS]:
        if k in tr and k != "Why":
            label = LABEL.get(k, k[4:].lower())
            print("  " + paint("| " + label.ljust(9), "dim") + " " + tr[k])
    return 0


def cmd_log(args):
    first = True
    for rec in log_records(args.range):
        tr, _ = first_of_each(rec["trailers"])
        if not first:
            print()
        first = False
        why = tr.get("Why") or paint("(no why recorded)", "red")
        print(f"{paint(rec['short'], 'yellow')}  {rec['date']}  {why}")
        if tr.get("Why-Rationale"):
            print("          " + paint("rationale: " + tr["Why-Rationale"], "dim"))
        meta = [f"{LABEL[k]}: {tr[k]}" for k in ("Why-Agent", "Why-Session", "Why-Spec") if tr.get(k)]
        if meta:
            print("          " + paint("   ".join(meta), "dim"))
    if first:
        print("no commits")
    return 0


def cmd_check(args):
    if args.range:
        rng = args.range
    elif git_ok("rev-parse", "--verify", "--quiet", "@{upstream}"):
        rng = ["@{upstream}..HEAD"]
    else:
        rng = ["-1", "HEAD"]
    bad, total = [], 0
    for rec in log_records(rng):
        total += 1
        if not any(k == "Why" for k, _ in rec["trailers"]):
            bad.append(rec)
    if bad:
        sys.stderr.write(paint(f"x {len(bad)}/{total} commit(s) missing a Why: trailer\n", "red"))
        for rec in bad:
            sys.stderr.write(f"  {rec['short']}  {rec['subject']}\n")
        return 1
    print(paint(f"ok - all {total} commit(s) carry a Why", "green"))
    return 0


def cmd_commit(args):
    pairs = [("Why", args.because), ("Why-Prompt", args.prompt),
             ("Why-Rationale", args.rationale), ("Why-Alternatives", args.alternatives),
             ("Why-Spec", args.spec),
             ("Why-Agent", args.agent or git("config", "--get", "why.agent", check=False).strip()),
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
    strict = "false" if args.no_strict else "true"
    git("config", "why.strict", strict)
    print(f"why.strict = {strict}")
    if args.agent:
        git("config", "why.agent", args.agent)
        print(f"why.agent = {args.agent}")
    return 0


def main():
    argv = sys.argv[1:]
    if not argv or argv[0] not in SUBCOMMANDS:
        if argv and argv[0] in ("-h", "--help"):
            return cmd_show("-h")
        return cmd_show(argv[0] if argv else None)

    p = argparse.ArgumentParser(prog="git why", add_help=True)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("log", help="timeline of recorded reasoning")
    sp.add_argument("range", nargs="*")
    sp.set_defaults(fn=cmd_log)

    sp = sub.add_parser("check", help="fail if any commit in range lacks a Why:")
    sp.add_argument("range", nargs="*")
    sp.set_defaults(fn=cmd_check)

    sp = sub.add_parser("init", help="install the commit-msg enforcement hook")
    sp.add_argument("--no-strict", action="store_true",
                    help="install the hook but leave why.strict off")
    sp.add_argument("--agent", help="set why.agent (default stamped on every commit)")
    sp.set_defaults(fn=cmd_init)

    sp = sub.add_parser("commit", help="git commit + a Why: trailer")
    sp.add_argument("-m", "--message")
    sp.add_argument("-b", "--because", help="the Why: line (why this change exists)")
    sp.add_argument("--prompt", help="the instruction that produced the change")
    sp.add_argument("--rationale", help="why this approach")
    sp.add_argument("--alternatives", help="what was considered and rejected")
    sp.add_argument("--spec", help="requirement / issue this satisfies")
    sp.add_argument("--agent")
    sp.add_argument("--session")
    sp.add_argument("--confidence", choices=["low", "medium", "high", "human-reviewed"])
    sp.add_argument("git_args", nargs=argparse.REMAINDER,
                    help="args after -- go straight to git commit")
    sp.set_defaults(fn=cmd_commit)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main() or 0)
