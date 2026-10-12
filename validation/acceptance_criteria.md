# Acceptance criteria — FROZEN BEFORE THE FIRST REAL RUN

Status: **DRAFT** — fill the `TBD` cells in milestone M3, commit, tag the commit
`criteria-frozen`, and do not edit thresholds after that. A threshold chosen after
seeing the data is a description, not a criterion. Later changes go in a dated
amendment table at the bottom, with the reason.

**Standing limitation:** a retrospective package on public benchmark data at these
sample sizes shows the pipeline recovers one known event. It does not substitute for
a prospective validation, and it is not a clinical or public-health service.

## Arms

| Arm | What it is | n | Truth source |
|---|---|---|---|
| SENS | Timme 2017 *L. monocytogenes* stone-fruit isolates labelled outbreak | 28 | Timme RE et al., PeerJ 2017;5:e3893, Table S-sheet |
| SPEC-T | Timme outgroups | 3 | same |
| SPEC-A | Added public non-outbreak isolates, same clonal complex, chosen by the rule below **before** running | TBD (≥ 35 recommended) | NCBI Pathogen Detection: different SNP cluster from the event — an **assumption** of unrelatedness, stated as such |

Selection rule for SPEC-A (write it before downloading): TBD — e.g. "first N isolates
of CC<x> in NCBI Pathogen Detection with paired Illumina reads, collected 20xx–20xx,
not in SNP cluster PDS<y>, sorted by accession".

## What each arm can bear (computed before running)

Wilson 95% lower bound if every isolate in the arm is called correctly:

| Arm | n | Best-case lower bound | Consequence |
|---|---|---|---|
| SENS | 28 | 0.879 | A "lower bound ≥ 0.90" criterion is **unattainable** at n = 28. Use a point criterion (28/28) and report the bound beside it |
| SPEC-T | 3 | 0.439 | Cannot support any specificity claim on its own |
| SPEC-T + SPEC-A | 38 | ~0.91 | 35 is the smallest flawless n whose bound clears 0.90 |

## Register

| ID | Criterion | Metric | Threshold | Arm | Computed by |
|---|---|---|---|---|---|
| AC1 | Assembly QC | total length, contigs, N50, est. depth, cgMLST loci called | TBD (set from literature/Phase 0, e.g. length within expected Lm range; loci called ≥ 95 %) | all | `results/qc_summary.csv` |
| AC2 | Typing consistency | MLST ST matches the public record for each isolate | 100 % | all | `results/typing_check.csv` |
| AC3 | Outbreak recovery | outbreak isolates in one cgMLST cluster at the frozen threshold T | 28/28 (report Wilson bound) | SENS | `bin/cluster_metrics.py` → `threshold_sweep.csv` |
| AC4 | Exclusion | non-outbreak isolates outside that cluster at T | TBD | SPEC-T + SPEC-A | same |
| AC5 | Method agreement | cgMLST cluster at T vs SNP cluster at S give the same membership | TBD (e.g. identical outbreak membership) | all | `results/method_agreement.csv` |
| AC6 | Threshold robustness | outbreak membership unchanged for T−2 … T+2 | yes/no | SENS + SPEC | ReporTree `stableRegions` + sweep |
| AC7 | Reproducibility | second run from the same commit gives identical cgMLST matrix (sha256) and partitions | identical | all | `results/rerun_check.csv` |

Frozen cgMLST threshold T = **TBD** (cite the source: the commonly used 7-allele
*L. monocytogenes* threshold — find and cite its primary reference yourself).
Paired SNP threshold S = **TBD** (with source).

## Amendments after freezing

| Date | Change | Reason | Effect on results |
|---|---|---|---|
