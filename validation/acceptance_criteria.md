# Acceptance criteria — FROZEN BEFORE THE FIRST REAL RUN

Status: **DRAFT** — values sourced 2026-10-16; ready to freeze. Fill the `TBD` cells in milestone M3, commit, tag the commit
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
| SPEC-A | Added public non-outbreak isolates, same clonal complex, chosen by the rule below **before** running | 5 (rule asked for 40; only 5 CC183 SNP clusters exist in PDG000000001.4942, see `data/spec_a_query.md`) | NCBI Pathogen Detection: different SNP cluster from the event — an **assumption** of unrelatedness, stated as such |

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
3. **Metadata filter** (snapshot files only, no network). Keep isolates that:
   - are not in the Timme sheet;
   - have a SNP cluster in `reference_target.cluster_list.tsv` that is neither
     **PDS000024934** nor **PDS000024956** (the outbreak's clusters, taken from the 28
     SENS isolates);
   - have a `collection_date` whose first four characters are a year from 2010 to 2016
     (a year-month or year alone counts; missing or unparseable dates are excluded);
   - have a non-empty `asm_acc` and at least one SRA run in `Run`.

   **Typing** (used in steps 4 and 5): `mlst --scheme listeria_2` on the `asm_acc` assembly
   with `staphb/mlst:2.35.0` (digest
   `sha256:d11a9ea089158c8648852f44ea7de495ea60001acb9850127b73b904e7c73642`); ST → CC with
   the Pasteur BIGSdb API (`pubmlst_listeria_seqdef`, scheme 2). A result counts only if
   the ST is exactly assigned and has a CC.
4. **Cluster CC.** **Assumption, stated as such:** a Pathogen Detection SNP cluster does not
   span clonal complexes. Clusters are single-linkage at about 50 SNPs; CCs differ by
   thousands. For each SNP cluster among the survivors, type its survivors in ascending
   BioSample order until one gives a result that counts, trying at most 3. That result is
   the cluster's CC. A cluster with no counting result in 3 tries is excluded and listed.
   Only clusters whose CC is CC183 go on to step 5.
5. **Selection walk.** Sort the survivors in CC183 clusters by BioSample accession,
   ascending, and walk down the list. For each isolate:
   a. skip it if an isolate from its SNP cluster has already been selected (one per
      cluster, so near-duplicates don't inflate specificity);
   b. **sequencing check:** its first SRA run in `Run` must be ILLUMINA and PAIRED in the
      ENA catalogue (`instrument_platform`, `library_layout`); otherwise skip it;
   c. **confirm:** type the isolate itself. It must count and be CC183, otherwise skip it
      and record it as evidence against the assumption in step 4;
   d. select it.
   Stop when 40 isolates are selected.
6. **Size.** N = 40. If the list runs out before 40, stop and report the shortfall;
   do not widen any filter without a dated amendment.
7. **Replacement.** An isolate that fails staging (md5, read count or pairing) or AC1 QC
   is replaced by the next isolate in the sorted list. Every replacement is logged with
   its reason. AC4's denominator is the isolates that passed QC, and that number is
   reported.

**Outcome (2026-10-16):** the rule yielded 5 of 40 (shortfall, step 6). Accepted as is;
no filter widened. 4 of the 5 are ST382, the outbreak's ST, in other SNP clusters.

## What each arm can bear (computed before running)

Wilson 95% lower bound if every isolate in the arm is called correctly:

| Arm | n | Best-case lower bound | Consequence |
|---|---|---|---|
| SENS | 28 | 0.879 | A "lower bound ≥ 0.90" criterion is **unattainable** at n = 28. Use a point criterion (28/28) and report the bound beside it |
| SPEC-T | 3 | 0.439 | Cannot support any specificity claim on its own |
| SPEC-T + SPEC-A | 8 | 0.676 | **No specificity claim is possible.** AC4 is a counterexample check: any non-outbreak isolate inside the outbreak cluster at T is a failure; a pass means none seen in 8, not that specificity is established. (Planned n = 43, bound 0.918; shortfall recorded 2026-10-16.) |

## Register

| ID | Criterion | Metric | Threshold | Arm | Computed by |
|---|---|---|---|---|---|
| AC1 | Assembly QC | total length, contigs, N50, est. depth, cgMLST loci called | all six gates below | all | `results/qc_summary.csv` |
| AC2 | Typing consistency | MLST ST matches the public record for each isolate | 100 % | all | `results/typing_check.csv` |
| AC3 | Outbreak recovery | outbreak isolates in one cgMLST cluster at the frozen threshold T | 28/28 (report Wilson bound) | SENS | `bin/cluster_metrics.py` → `threshold_sweep.csv` |
| AC4 | Exclusion | non-outbreak isolates outside that cluster at T | 8/8 (0 of 3 SPEC-T + 5 SPEC-A in the cluster); report Wilson bound 0.676 and "a pass means no counterexample in 8 isolates; specificity is not established"; any isolate in the cluster is named | SPEC-T + SPEC-A | same |
| AC5 | Method agreement | cgMLST cluster at T vs SNP cluster at S give the same membership | identical outbreak-cluster membership over all QC-passing isolates; discordant isolates listed with both distances. Correlation of pairwise distances reported descriptively, no threshold | all | `results/method_agreement.csv` |
| AC6 | Threshold robustness | outbreak membership unchanged for T−2 … T+2 | yes/no | SENS + SPEC | ReporTree `stableRegions` + sweep |
| AC7 | Reproducibility | second run from the same commit gives identical cgMLST matrix (sha256) and partitions | identical | all | `results/rerun_check.csv` |

### AC1 QC gates (an isolate must pass all five)

| Gate | Threshold | Basis |
|---|---|---|
| Species check (Kraken2) | top species *L. monocytogenes*, and every other species < 1 % of classified reads | adapted from PulseNet 2.0's contamination gate (MIDAS secondary coverage < 1.0 %) [1]; a different tool, so the adaptation is ours |
| Total assembly length | 2.8–3.19 Mb | PulseNet 2.0 *Lm* criteria [1] |
| Contigs (≥ 500 bp) | ≤ 400 | Institut Pasteur BIGSdb *Listeria* genome quality criteria [2] |
| Estimated depth after trimming | > 20× | PulseNet 2.0 (average de novo coverage > 20×) [1]; PulseNet PNQ07 target ≥ 20× [3]. One low-depth isolate shrinks the SNP core for every isolate (Phase 0 §3d) |
| cgMLST loci called | > 95 % (≥ 1,661 of 1,748) | PulseNet 2.0 (> 95 % core-genome alleles called, same 1,748-locus scheme) [1]; also bounds the count-vs-proportion drift (below, Phase 0 §3b) |

No N50 gate: neither PulseNet 2.0 nor Pasteur uses one, and no source was found.

[1] Appendix to *Retrospective Analysis of Historical Listeria monocytogenes Clinical
    Isolates, New York, USA, 2000–2021*. Emerg Infect Dis 2025;31(10).
    doi:10.3201/eid3110.241876. Secondary source: it reports the PulseNet 2.0 QC criteria
    but cites no primary QC document.
[2] https://bigsdb.pasteur.fr/listeria/genomes-quality-criteria/ (accessed 2026-10-16).
[3] PulseNet SOP PNQ07, Illumina MiSeq Data QC (effective 2015; may have been superseded).

Frozen cgMLST threshold **T = 7 alleles**: Pasteur cgMLST1748, single linkage, ReporTree
partition `MST-7x1.0`. Source: Moura A et al. *Nat Microbiol* 2016;2:16185, where 7 is a
proportion of the 1,748 loci (0.400 %). ReporTree applies it as a count of differing loci
among loci called in both profiles (Phase 0 §3b). At the AC1 floor of 1,661 shared loci,
7 mismatches is 0.421 %, so the drift from Moura's definition is at most ~0.4 alleles.

Paired SNP threshold **S = 20 SNPs**: snippy-core alignment, snp-dists, single linkage.
Source: Pightling AW et al. *Front Microbiol* 2018;9:1482 (doi:10.3389/fmicb.2018.01482).
In FDA CFSAN's framework, fewer than 21 SNPs *supports* a match, as one of three lines of
evidence with tree topology and bootstrap support. The authors warn against SNP thresholds
alone. Using it here as a single-linkage cut is our adaptation, not their cluster
definition. S = 20 was drafted before Chen et al. 2016 was read (Phase 0 §5). Chen reports
up to 42 SNPs within this outbreak, so AC5 may legitimately fail. S is not raised to fit.

## Amendments after freezing

| Date | Change | Reason | Effect on results |
|---|---|---|---|
