#!/bin/sh
# Runnable check for git-why. No framework: builds a throwaway repo and
# exercises init / commit / show / log / check end to end.
set -eu

SCRIPT="$(cd "$(dirname "$0")/.." && pwd)/git_why.py"
gw() { python3 "$SCRIPT" "$@"; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
cd "$tmp"
git init -q
git config user.email t@example.com
git config user.name Tester

# init: hook installed, strict on
gw init >/dev/null
[ "$(git config --bool why.strict)" = "true" ] || { echo "FAIL: strict not set"; exit 1; }

# strict blocks a commit with no Why:
echo a >a.txt && git add a.txt
if git commit -q -m "no why" 2>/dev/null; then echo "FAIL: hook did not block"; exit 1; fi

# git why commit writes the trailer
gw commit -m "add a.txt" -b "need a base file to build on" \
   --rationale "smallest thing that makes the tree non-empty" \
   --agent "claude-sonnet-5" --session "smoke-1" >/dev/null
git log -1 --format=%B | grep -q "^Why: need a base file to build on" \
  || { echo "FAIL: Why trailer missing from commit"; exit 1; }

# reader: by revision and by path
gw HEAD    | grep -q "need a base file" || { echo "FAIL: git why HEAD"; exit 1; }
gw a.txt   | grep -q "need a base file" || { echo "FAIL: git why <path>"; exit 1; }
gw HEAD    | grep -q "rationale"        || { echo "FAIL: extra trailer not shown"; exit 1; }

# log
gw log | grep -q "need a base file" || { echo "FAIL: git why log"; exit 1; }

# check passes on a clean history
gw check >/dev/null || { echo "FAIL: check should pass"; exit 1; }

# check fails once a Why-less commit sneaks in (--no-verify bypasses the hook)
echo b >b.txt && git add b.txt && git commit -q -m "sneaky" --no-verify
if gw check "HEAD~1..HEAD" >/dev/null 2>&1; then echo "FAIL: check missed a bad commit"; exit 1; fi

echo "SMOKE OK"
