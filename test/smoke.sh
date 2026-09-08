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
big() { printf '%s line %s\n' "$1" $(seq 1 40) > "$1"; git add "$1"; }

# --- version ---------------------------------------------------------------
gw --version | grep -qE "^git why [0-9]+\.[0-9]+" || fail "git why --version"

# ---- default: nudge (never blocks) -------------------------------------
gw init >/dev/null
[ "$(git config --get why.strict)" = "nudge" ] || fail "default level is not nudge"

echo hi > README.md && git add README.md
out=$(git commit -m "add readme" 2>&1) || fail "nudge blocked a trivial commit"
if printf '%s' "$out" | grep -qi "git-why"; then fail "nudge nagged on a trivial change"; fi

big core.py
out=$(git commit -m "add core.py" 2>&1) || fail "nudge blocked a substantial commit"
printf '%s' "$out" | grep -qi "no reason recorded" || fail "nudge printed no tip"

big helper.py
gw commit -m "add helper.py" -b "split out of core.py so tests can import it alone" \
   --agent "claude-sonnet-5" --session "s1" >/dev/null
git log -1 --format=%B | grep -q "^Why: split out of core" || fail "reason not recorded"

# ---- --enforce: blocks substantial, still ignores trivial -------------
gw init --enforce >/dev/null
[ "$(git config --get why.strict)" = "substantial" ] || fail "--enforce did not set substantial"

big feature.py
if git commit -m "add feature.py" >/dev/null 2>&1; then fail "enforce let a reasonless substantial commit through"; fi
if gw commit -m "add feature.py" -b "add feature.py" >/dev/null 2>&1; then fail "reason echoing the subject was accepted"; fi
if gw commit -m "add feature.py" -b "updates" >/dev/null 2>&1; then fail "filler reason was accepted"; fi
gw commit -m "add feature.py" -b "the feature the whole task was about; entry point for the CLI" >/dev/null

big vendored.py
gw commit -m "vendor upstream helper" --skip "copied verbatim from upstream, not our code" >/dev/null
git log -1 --format=%B | grep -q "^Why-Skip: copied verbatim" || fail "Why-Skip not recorded"

echo "more" >> README.md && git add README.md
git commit -m "tweak readme" >/dev/null 2>&1 || fail "enforce blocked a trivial change"

# ---- reader / log / export -------------------------------------------
gw helper.py | grep -q "split out of core" || fail "git why <path>"
gw log | grep -q "split out of core" || fail "git why log"
gw log --agent claude | grep -q "split out of core" || fail "git why log --agent"
gw log --agent nope | grep -q "no matching commits" || fail "git why log --agent filter"
gw export | python3 -c "import sys,json; [json.loads(l) for l in sys.stdin if l.strip()]" \
  || fail "git why export is not valid NDJSON"
gw export | grep -q '"why_agent": "claude-sonnet-5"' || fail "export missing why_agent"

# ---- CI check ------------------------------------------------------------
gw check --level nudge | grep -qi "not a CI gate" || fail "check --level nudge should no-op"
gw check >/dev/null || fail "check should pass on clean history at substantial"
big sneaky.py
git commit -m "sneaky big change" --no-verify >/dev/null
if gw check "HEAD~1..HEAD" >/dev/null 2>&1; then fail "check missed a reasonless substantial commit"; fi

# ---- --all is stricter than substantial -------------------------------
other="$(mktemp -d)"; cd "$other"; git init -q
git config user.email a@a.a; git config user.name A
gw init --all >/dev/null
echo hi > a && git add a
if git commit -m "tiny" >/dev/null 2>&1; then fail "--all did not require a reason on a trivial change"; fi
rm -rf "$other"

echo "SMOKE OK"
