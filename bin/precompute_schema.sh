#!/usr/bin/env bash
# Pre-compute chewBBACA's schema caches once, outside the pipeline (M4).
#
# On first use, AlleleCall writes loci_modes and pre_computed/ into the schema directory,
# even with --no-inferred, and fails on a read-only schema (phase0_findings.md §3a).
# Nextflow stages the schema as a symlink, so a pipeline run would otherwise modify the
# canonical schema. This script triggers those writes once, then proves the schema is
# stable: a second AlleleCall on a READ-ONLY mount must succeed and change nothing.
#
# Usage: bin/precompute_schema.sh <schema_dir> <genome1.fasta> <genome2.fasta>
# Prints the tree checksum before and after; record the "after" value in
# validation/version_lock.json.
set -euo pipefail

IMG="quay.io/biocontainers/chewbbaca@sha256:7319470168718affb429d4dab8bd78834dd31ceea576917afe4cea3525fe7d95"
schema=$(cd "$1" && pwd)
g1=$(cd "$(dirname "$2")" && pwd)/$(basename "$2")
g2=$(cd "$(dirname "$3")" && pwd)/$(basename "$3")
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

tree_sha() {  # sha256 of per-file sha256 list, LC_ALL=C sorted paths
    (cd "$1" && find . -type f | LC_ALL=C sort | xargs shasum -a 256) | shasum -a 256 | cut -c1-64
}

run_allelecall() {  # $1 genome, $2 mount mode (rw|ro), $3 output name
    mkdir -p "$work/in_$3"
    cp "$1" "$work/in_$3/"
    docker run --rm --platform linux/amd64 \
        -v "$schema":/schema:"$2" -v "$work":/w -w /w "$IMG" \
        chewBBACA.py AlleleCall -i "in_$3" -g /schema -o "out_$3" --no-inferred --cpu 4 \
        > "$work/$3.log" 2>&1 || { tail -20 "$work/$3.log"; return 1; }
}

before=$(tree_sha "$schema")
echo "before:            $before"

run_allelecall "$g1" rw first
after_first=$(tree_sha "$schema")
echo "after first call:  $after_first  (cache files written)"
(cd "$schema" && ls -d loci_modes pre_computed 2>/dev/null) | sed 's/^/  created: /'

run_allelecall "$g2" ro second
after_second=$(tree_sha "$schema")
echo "after second call: $after_second  (read-only mount)"

if [ "$after_first" != "$after_second" ]; then
    echo "FAIL: schema changed on the second call" >&2
    exit 1
fi
echo "OK: schema stable after pre-compute; record $after_first"
