#!/bin/sh
# Runnable check for git-why. No framework: builds throwaway repos and
# exercises init / commit / show / log / check / export end to end.
set -eu

SCRIPT="$(cd "$(dirname "$0")/.." && pwd)/git_why.py"
gw() { python3 "$SCRIPT" "$@"; }
fail() { echo "FAIL: $1"; exit 1; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# put a `git-why` shim on PATH so the commit-msg hook resolves it, the way a
# real install (pipx / copy to ~/.local/bin) would.
mkdir -p "$tmp/bin"
printf '#!/bin/sh\nexec python3 "%s" "$@"\n' "$SCRIPT" > "$tmp/bin/git-why"
chmod +x "$tmp/bin/git-why"
export PATH="$tmp/bin:$PATH"

cd "$tmp"
git init -q
git config user.email t@example.com
git config user.name Tester

# --- version ---------------------------------------------------------------
gw --version | grep -qE "^git why [0-9]+\.[0-9]+" || fail "git why --version"

# --- default (substantial) enforcement -----------------------------------
gw init >/dev/null
[ "$(git config --get why.strict)" = "substantial" ] || fail "default level not substantial"

# a TRIVIAL change is allowed with no reason
echo "hi" > README.md && git add README.md
git commit -q -m "add readme" || fail "trivial commit was blocked"

# a SUBSTANTIAL change with no reason is blocked
printf 'line %s\n' $(seq 1 40) > big.py && git add big.py
if git commit -q -m "add big.py" 2>/dev/null; then fail "substantial commit not blocked"; fi

# ... and allowed once a reason is given
gw commit -m "add big.py" -b "core module every other file will import" \
   --rationale "kept flat on purpose" --agent "claude-sonnet-5" --session "s1" >/dev/null
git log -1 --format=%B | grep -q "^Why: core module" || fail "Why trailer missing"

# a low-effort reason on a substantial change is blocked (echoes the subject)
printf 'x %s\n' $(seq 1 40) > big2.py && git add big2.py
if gw commit -m "add big2.py" -b "add big2.py" >/dev/null 2>&1; then fail "echo-subject reason accepted"; fi
if gw commit -m "add big2.py" -b "updates" >/dev/null 2>&1; then fail "filler reason accepted"; fi
gw commit -m "add big2.py" -b "second half of the core module, split for readability" >/dev/null

# Why-Skip lets a substantial change through and is recorded
printf 'y %s\n' $(seq 1 40) > vendored.py && git add vendored.py
gw commit -m "vendor upstream helper" --skip "copied verbatim from upstream, not our code" >/dev/null
git log -1 --format=%B | grep -q "^Why-Skip: copied verbatim" || fail "Why-Skip not recorded"

# --- reader / log / export --------------------------------------------------
gw HEAD~2 | grep -q "core module" || fail "git why <rev>"
gw big.py | grep -q "core module" || fail "git why <path>"
gw log | grep -q "core module" || fail "git why log"
gw log --agent claude | grep -q "core module" || fail "git why log --agent"
gw log --agent nope | grep -q "no matching commits" || fail "git why log --agent filter"
gw export | python3 -c "import sys,json; [json.loads(l) for l in sys.stdin if l.strip()]" \
  || fail "git why export is not valid NDJSON"
gw export | grep -q '"why_agent": "claude-sonnet-5"' || fail "export missing why_agent"

# --- CI check ------------------------------------------------------------
gw check >/dev/null || fail "check should pass on clean history"
printf 'z %s\n' $(seq 1 40) > sneaky.py && git add sneaky.py
git commit -q -m "sneaky big change" --no-verify
if gw check "HEAD~1..HEAD" >/dev/null 2>&1; then fail "check missed a substantial reasonless commit"; fi

# --- level=all is stricter -------------------------------------------------
other="$(mktemp -d)"; cd "$other"; git init -q
git config user.email t@e.t; git config user.name T
gw init --all >/dev/null
echo hi > a && git add a
if git commit -q -m "tiny" 2>/dev/null; then fail "--all did not require a reason for a trivial change"; fi
rm -rf "$other"

echo "SMOKE OK"
