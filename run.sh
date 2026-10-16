#!/usr/bin/env bash
# Gated validation run (M4/M5). Refuses to start unless:
#   1. the working tree is clean;
#   2. HEAD is validation/version_lock.json "pipeline_commit", or descends from it with
#      only the lock file changed;
#   3. the cgMLST schema at params "schema_dir" has the tree checksum recorded as
#      databases.chewbbaca_schema.precomputed_tree_sha256 (bin/precompute_schema.sh).
# Every reported number must trace to a run that passed these gates (CLAUDE.md rule 2).
#
# Usage: ./run.sh <params.yml> [extra nextflow args...]
#   PROFILE  Nextflow profiles (default: listeria,docker; on Apple Silicon add emulate_amd64)
# The params file must set outdir and schema_dir (plain "key: value" lines).
set -euo pipefail

cd "$(dirname "$0")"
LOCK=validation/version_lock.json
PROFILE="${PROFILE:-listeria,docker}"

die() { echo "run.sh: REFUSED - $*" >&2; exit 1; }

[ $# -ge 1 ] || die "usage: ./run.sh <params.yml> [extra nextflow args...]"
params=$1; shift
[ -f "$params" ] || die "params file not found: $params"

lock() {  # read a dotted key from the version lock
    python3 -c 'import json,sys
d=json.load(open(sys.argv[1]))
for k in sys.argv[2].split("."): d=d.get(k, {}) if isinstance(d, dict) else {}
print(d if isinstance(d, str) else "")' "$LOCK" "$1"
}
param() {  # read "key: value" from the params file (no nesting)
    python3 -c 'import re,sys
for line in open(sys.argv[1]):
    m=re.match(r"^\s*"+re.escape(sys.argv[2])+r"\s*:\s*(.*?)\s*$", line)
    if m: print(m.group(1).strip("\"'"'"'")); break' "$params" "$1"
}
tree_sha() {
    (cd "$1" && find . -type f | LC_ALL=C sort | xargs shasum -a 256) | shasum -a 256 | cut -c1-64
}

# 1. clean tree
[ -z "$(git status --porcelain)" ] || die "working tree is not clean (commit or stash first)"

# 2. commit gate
head=$(git rev-parse HEAD)
pinned=$(lock pipeline_commit)
[ -n "$pinned" ] && [ "$pinned" != "TBD" ] || die "pipeline_commit is not set in $LOCK"
# Committing the lock moves HEAD, so HEAD may be a descendant of the pinned commit
# provided nothing but the lock file differs: the code that runs is the pinned code.
git merge-base --is-ancestor "$pinned" HEAD 2>/dev/null \
    || die "pinned pipeline_commit $pinned is not HEAD or an ancestor of HEAD $head"
changed=$(git diff --name-only "$pinned" HEAD -- . ":(exclude)$LOCK")
[ -z "$changed" ] || die "files changed since pinned commit $pinned: $(echo $changed)"

# 3. schema gate
schema=$(param schema_dir)
outdir=$(param outdir)
[ -n "$outdir" ] || die "outdir not set in $params"
[ -n "$schema" ] && [ -d "$schema" ] || die "schema_dir not set or not a directory: '$schema'"
expected=$(lock databases.chewbbaca_schema.precomputed_tree_sha256)
[ -n "$expected" ] || die "precomputed_tree_sha256 not recorded in $LOCK"
echo "run.sh: checking schema checksum (a few seconds per GB)..."
actual=$(tree_sha "$schema")
[ "$actual" = "$expected" ] || die "schema $schema checksum $actual != recorded $expected"

echo "run.sh: gates passed - code at $pinned (HEAD $head), schema $actual"
mkdir -p "$outdir/pipeline_info"
{
    echo "pipeline_commit: $pinned"
    echo "head: $head"
    echo "schema_tree_sha256: $actual"
    echo "params_file: $params"
    echo "params_sha256: $(shasum -a 256 "$params" | cut -c1-64)"
    echo "profile: $PROFILE"
    echo "nextflow: $(nextflow -version 2>&1 | grep -o 'version [0-9.]*' | head -1)"
    echo "started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$outdir/pipeline_info/run_gate.txt"

exec nextflow run . -profile "$PROFILE" -params-file "$params" "$@"
