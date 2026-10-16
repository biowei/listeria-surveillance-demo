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
| SPEC-A | Added public non-outbreak isolates, same clonal complex, chosen by the rule below **before** running | 40 | NCBI Pathogen Detection: different SNP cluster from the event — an **assumption** of unrelatedness, stated as such |

Selection rule for SPEC-A — committed before any candidate isolate was viewed (the git
commit that adds this rule is its timestamp). Applied mechanically; no isolate is added
or removed by judgement.

1. **Source.** NCBI Pathogen Detection, *Listeria* isolate browser, snapshot
   `PDG000000001.4942` (current on 2026-10-16). Query and date are recorded in
   `data/spec_a_query.md`.
2. **Clonal complex.** CC = **CC183**: the CC of the outbreak strain, from `mlst` on
   the public GenBank assemblies of three SENS isolates (GCA_001257525.1,
   GCA_001257505.1, GCA_001257515.1; all ST382) plus the ST→CC table of the Pasteur
   BIGSdb scheme. If those isolates disagree on CC, stop and amend.
3. **Include:** *L. monocytogenes*; ST in that CC; at least one SRA run that is Illumina
   paired-end; collection year 2010–2016.
4. **Exclude:** any isolate in the Timme sheet; any isolate in the outbreak's SNP
   cluster(s) **PDS000024934 and PDS000024956** (taken from the 28 SENS isolates); any
   isolate not assigned to a SNP cluster.
5. **One per SNP cluster.** Keep only the lowest-accession isolate in each SNP cluster,
   so that specificity isn't inflated by near-duplicate isolates.
6. **Order and size.** Sort by BioSample accession, ascending, and take the first N = 40.
7. **Replacement.** An isolate that fails staging (md5, read count or pairing) or AC1 QC
   is replaced by the next isolate in the sorted list. Every replacement is logged with
   its reason. AC4's denominator is the isolates that passed QC, and that number is
   reported.

## What each arm can bear (computed before running)

Wilson 95% lower bound if every isolate in the arm is called correctly:

| Arm | n | Best-case lower bound | Consequence |
|---|---|---|---|
| SENS | 28 | 0.879 | A "lower bound ≥ 0.90" criterion is **unattainable** at n = 28. Use a point criterion (28/28) and report the bound beside it |
| SPEC-T | 3 | 0.439 | Cannot support any specificity claim on its own |
| SPEC-T + SPEC-A | 43 | 0.918 | N = 40 chosen over the minimum 35 (the smallest flawless SPEC-A n whose combined bound clears 0.90) to leave a margin for QC losses |

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
