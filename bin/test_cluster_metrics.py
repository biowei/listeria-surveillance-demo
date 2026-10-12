#!/usr/bin/env python3
"""Regression suite for bin/cluster_metrics.py.

Plain script, no pytest needed:  python3 bin/test_cluster_metrics.py
Exits 1 on any failure. Milestone M5: make every test pass BEFORE trusting any
number the module produces, and add a test whenever you add a metric.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
FIXTURE = os.path.join(HERE, "..", "assets", "test_fixtures", "partitions_toy.tsv")

import cluster_metrics as cm  # noqa: E402

FAILS = []


def check(name, got, expected):
    if got == expected:
        print(f"PASS  {name}")
    else:
        print(f"FAIL  {name}: got {got!r}, expected {expected!r}")
        FAILS.append(name)


def run(name, fn):
    try:
        fn()
    except NotImplementedError:
        print(f"TODO  {name}: not implemented yet")
        FAILS.append(name)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR {name}: {type(exc).__name__}: {exc}")
        FAILS.append(name)


# --- Wilson lower bound (already implemented) --------------------------------
def t_wilson():
    check("wilson 28/28", round(cm.wilson_lower(28, 28), 3), 0.879)
    check("wilson 3/3", round(cm.wilson_lower(3, 3), 3), 0.439)
    check("wilson 35/35", round(cm.wilson_lower(35, 35), 3), 0.901)
    check("wilson 0/10", cm.wilson_lower(0, 10), 0.0)
    check("wilson n=0", cm.wilson_lower(0, 0), 0.0)


# --- outbreak_cluster ---------------------------------------------------------
TRUTH = {"A": True, "B": True, "C": True, "D": True, "E": False, "F": False, "G": False}


def t_outbreak_cluster():
    p7 = {"A": "cluster_1", "B": "cluster_1", "C": "cluster_1", "D": "cluster_1",
          "E": "cluster_1", "F": "cluster_2", "G": "cluster_2"}
    check("outbreak cluster picks majority-outbreak cluster", cm.outbreak_cluster(p7, TRUTH), "cluster_1")
    all_single = {s: f"singleton_{i}" for i, s in enumerate(TRUTH)}
    check("singletons are never the outbreak cluster", cm.outbreak_cluster(all_single, TRUTH), None)


# --- confusion ----------------------------------------------------------------
def t_confusion():
    p0 = {"A": "singleton_1", "B": "cluster_1", "C": "cluster_1", "D": "singleton_2",
          "E": "singleton_3", "F": "singleton_4", "G": "singleton_5"}
    check("confusion thr0", cm.confusion(p0, TRUTH), {"tp": 2, "fn": 2, "tn": 3, "fp": 0})
    all_single = {s: f"singleton_{i}" for i, s in enumerate(TRUTH)}
    check("confusion all singletons", cm.confusion(all_single, TRUTH), {"tp": 0, "fn": 4, "tn": 3, "fp": 0})


# --- sweep over a ReporTree-style partitions table ----------------------------
def t_sweep():
    rows = cm.sweep(FIXTURE)
    check("sweep row count", len(rows), 2)
    by_t = {r["threshold"]: r for r in rows}
    check("sweep thr0 counts", {k: by_t[0][k] for k in ("tp", "fn", "tn", "fp")},
          {"tp": 2, "fn": 2, "tn": 3, "fp": 0})
    check("sweep thr7 counts", {k: by_t[7][k] for k in ("tp", "fn", "tn", "fp")},
          {"tp": 4, "fn": 0, "tn": 2, "fp": 1})
    check("sweep thr7 sensitivity", by_t[7]["sensitivity"], 1.0)
    check("sweep thr7 sensitivity lower bound", round(by_t[7]["sensitivity_lower"], 3), 0.510)
    check("sweep thr7 specificity", round(by_t[7]["specificity"], 3), 0.667)


for name, fn in [("wilson", t_wilson), ("outbreak_cluster", t_outbreak_cluster),
                 ("confusion", t_confusion), ("sweep", t_sweep)]:
    run(name, fn)

print()
if FAILS:
    print(f"{len(FAILS)} failing: {', '.join(FAILS)}")
    sys.exit(1)
print("all tests passed")
