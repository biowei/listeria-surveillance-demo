#!/usr/bin/env python3
"""Cluster-recovery metrics for the validation arm (milestone M5).

Question this answers: at each cgMLST allele threshold, does the pipeline put the
known outbreak isolates in one cluster and keep the non-outbreak isolates out of it?

Input: ReporTree `*_metadata_w_partitions.tsv` — one row per sample, a truth
column (validation only), and one partition column per threshold, named like
`MST-7x1.0` [verify the exact pattern against your own ReporTree output, then
adjust PARTITION_PATTERN].

YOUR TASK: implement outbreak_cluster(), confusion() and sweep() until
`python3 bin/test_cluster_metrics.py` prints "all tests passed".
wilson_lower() is done for you.

CLI (works once the functions are implemented):
    python3 bin/cluster_metrics.py results/clusters/lm_metadata_w_partitions.tsv \
        --out results/validation/threshold_sweep.csv
"""
import argparse
import csv
import re
from math import sqrt

PARTITION_PATTERN = r"^MST-(\d+)x"
POSITIVE_VALUES = ("yes", "true", "1")


def wilson_lower(k, n, z=1.959964):
    """Lower bound of the 95% Wilson score interval for k successes out of n.

    Returns 0.0 when n == 0. Worked values: 28/28 -> 0.879; 3/3 -> 0.439;
    35/35 -> 0.901 (the smallest flawless n that clears 0.90).
    """
    if n == 0:
        return 0.0
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    adj = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (centre - adj) / denom)


def outbreak_cluster(partition, truth):
    """Return the name of the cluster that represents the outbreak, or None.

    partition: dict sample -> cluster name ('cluster_N' or 'singleton_N')
    truth:     dict sample -> bool (True = outbreak isolate)

    Rules (decide them, write them down in acceptance_criteria.md, then code them):
      * the outbreak cluster is the non-singleton cluster holding the MOST
        truth-outbreak isolates;
      * a 'singleton_*' is never the outbreak cluster;
      * if no non-singleton cluster contains an outbreak isolate, return None;
      * if two clusters tie for the most outbreak isolates, return None
        (an ambiguous call is a failure, not a coin toss).
    """
    raise NotImplementedError


def confusion(partition, truth):
    """Return {'tp', 'fn', 'tn', 'fp'} counts.

    Predicted positive = sample is in outbreak_cluster(partition, truth).
    tp: outbreak isolate inside the outbreak cluster
    fn: outbreak isolate outside it (other cluster or singleton)
    fp: non-outbreak isolate inside it
    tn: non-outbreak isolate outside it
    If outbreak_cluster() is None, nothing is predicted positive.
    """
    raise NotImplementedError


def sweep(path, sample_col="sample", truth_col="truth_outbreak", pattern=PARTITION_PATTERN):
    """Read a ReporTree partitions TSV and return one dict per threshold, sorted by threshold.

    Each dict holds: threshold (int), outbreak_cluster, tp, fn, tn, fp,
    sensitivity, sensitivity_lower, specificity, specificity_lower.
    Sensitivity = tp / (tp + fn); specificity = tn / (tn + fp); 0.0 if the denominator is 0.
    Lower bounds come from wilson_lower(). Truth values are positive if they match
    POSITIVE_VALUES (case-insensitive). Columns that do not match `pattern` are ignored.
    """
    raise NotImplementedError


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("partitions_tsv")
    ap.add_argument("--out", required=True)
    ap.add_argument("--truth-col", default="truth_outbreak")
    args = ap.parse_args()
    rows = sweep(args.partitions_tsv, truth_col=args.truth_col)
    with open(args.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} thresholds to {args.out}")


if __name__ == "__main__":
    main()
