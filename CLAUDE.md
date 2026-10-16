# CLAUDE.md — listeria-surveillance-demo

Read this at the start of every session. Then run `git status` and `git log --oneline -5`,
and ask Wei which milestone (M0–M9) the session is for before changing anything.

## What this is

A **portfolio project on public benchmark data** by Wei Lu: an end-to-end *Listeria
monocytogenes* genomic surveillance workflow — reads → assembly → MLST / AMR / cgMLST /
SNP → clusters at thresholds → SQL data layer → one report for clinicians / infection
control and one for public health — validated against a known outbreak with acceptance
criteria frozen before the first real run.

It is **not** a clinical or public-health service, not a validation of any laboratory's
method, and not workplace experience. Every README, report and chart says so.

Base: **fork of nf-core/bacass 2.6.0** (MIT, "The nf-core/bacass team"), branch
`listeria-surveillance`. Keep the licence and the bacass credit in `README.md` and `CITATIONS.md`.

Plans (read before structural changes): `docs/fork_plan.md` (how bacass is adapted),
`docs/build_guide.md` (milestones M0–M9 and what "done" means for each).

## Who writes what — the most important rule

Wei must be able to explain and defend every core line in an interview.

**Wei writes these. Claude explains, reviews and suggests — in chat, as a proposed diff —
and does not create or rewrite them unless Wei says "write it" in that same message:**

- `modules/local/reportree/` and `modules/local/chewbbaca/extractcgmlst/` (main.nf, stub, tests)
- `subworkflows/local/population_surveillance/main.nf`
- the call to that subworkflow in `workflows/bacass.nf`
- `bin/cluster_metrics.py` — `outbreak_cluster()`, `confusion()`, `sweep()`
- `validation/acceptance_criteria.md` thresholds and the SPEC-A selection rule
- `validation/VALIDATION_REPORT.md` conclusions

**Claude may do directly (say what changed and why):** `nf-core modules install / update / patch`, `nextflow.config` and `nextflow_schema.json` plumbing (`nf-core pipelines schema build`),
`conf/modules.config` entries, `conf/listeria.config` and `conf/test_listeria.config`,
lint fixes, container/environment debugging, running tests and pipelines, reading logs,
staging scripts, the SQL loader, and docs that are not conclusions.

When teaching, explain the Nextflow / nf-core concept behind a fix in two or three
sentences (channels, meta maps, `collect`, `join`, topics, `ext.args`), not only the fix.

## nf-core conventions in this repo

- Install modules with `nf-core modules install`; never hand-edit `modules/nf-core/` —
  use `nf-core modules patch` if a change is unavoidable.
- Tool arguments, prefixes and `publishDir` go in `conf/modules.config` (`ext.args`), not in modules.
- New params: `null` default in `nextflow.config` **and** an entry in `nextflow_schema.json`;
  values come from a profile or `-params-file`.
- Short-read path is selected by the `listeria` profile (`conf/listeria.config`). **No bacass
  code is removed**; bacass's own nf-tests must keep passing.
- Versions are reported through the `versions` topic channel, as in bacass 2.6.0.
- Every local module has a `stub:` block, `meta.yml`, `environment.yml` and an nf-test.
- Join channels on `meta.id`; bacass also carries `meta.sample` and `meta.single_end`.

## Commands

```bash
nextflow run . -profile test,docker --outdir baseline              # unmodified bacass baseline (M0)
nextflow run . -profile test_listeria,docker -stub --outdir stub   # wiring only — proves nothing about tools
nextflow run . -profile test_listeria,docker --outdir test_out     # 3 real isolates
nf-test test                                                       # all nf-tests (bacass + ours)
nf-core modules test reportree                                     # one local module
nf-core pipelines lint
python3 bin/test_cluster_metrics.py                                # must print "all tests passed"
```

On Apple Silicon add `arm64` to the profile list, or run on Codespaces. Set
`process.resourceLimits` to the real machine.

## Validation rules (Wei's protocol — non-negotiable)

1. **Criteria are frozen before the first real run.** `validation/acceptance_criteria.md` is
   tagged `criteria-frozen`. Never change a threshold after seeing results; changes go in the
   dated amendments table with the reason, and Wei decides.
2. **Every reported number traces to a pinned commit.** `run.sh` refuses to start when
   `git rev-parse HEAD` differs from `validation/version_lock.json`. Never report figures
   from a dirty or unpinned tree.
3. **A stub run proves wiring only.** Never cite it as evidence of tool behaviour or accuracy.
4. **Re-derive every number** in a report from its CSV in `results/` before saving.
5. **Say what was not established**, in the same sentence as the result. Small arms get
   their Wilson lower bound beside the point estimate (28/28 → 0.879; 3/3 → 0.439).
6. **Never let one arm stand in for another.** If an arm is blocked, say so and stop; do not
   patch the pipeline to unblock it without asking Wei.

## Reproducibility

- Containers pinned by exact version; never `latest`.
- **AMRFinderPlus database pinned** (`--amrfinder_db`); do not run `AMRFINDERPLUS_UPDATE` in
  validation runs — it changes the database and breaks rerun identity.
- Fixed Snippy reference (Timme `suggestedReference`), checksum in `validation/phase0_findings.md`.
- chewBBACA `AlleleCall` with `--no-inferred`; ReporTree pinned at v2.6.0 (`insapathogenomics/reportree:v2.6.0`, digest in
  `validation/version_lock.json`; no v2.6.1 was ever released).
- Record every tool, container and database version in `validation/version_lock.json`.

## Data rules

- Public data only (Timme et al. 2017 *L. monocytogenes* set + NCBI Pathogen Detection
  isolates chosen by the frozen rule). **No RCPAQAP, AGRF or other former-employer data.**
- Staging verifies md5 and read count against the ENA catalogue and checks R1/R2 read-name
  pairing; on a pairing mismatch delete both mates. Manifest rebuilt from disk.
- FASTQ, schemas, databases, `work/` and `results/` are not committed (see `.gitignore`)
  until the final results tag.
- `truth_outbreak` is validation-only. Synthetic collection dates are flagged
  `date_is_synthetic = 1` and labelled on every chart.

## Git

- Small commits, one change each, message says what and why.
- Do not push, tag, or rewrite history without Wei's go-ahead.
- Never commit secrets, credentials or data files.

## Layout (after carry-over)

| Path                                                                     | Holds                                                                  |
| ------------------------------------------------------------------------ | ---------------------------------------------------------------------- |
| `conf/listeria.config`, `conf/test_listeria.config`                  | profiles for this project                                              |
| `subworkflows/local/population_surveillance/`                          | MLST, AMR, cgMLST, ReporTree, Snippy, snp-dists, IQ-TREE               |
| `modules/local/reportree/`, `modules/local/chewbbaca/extractcgmlst/` | the two modules nf-core lacks                                          |
| `bin/cluster_metrics.py`, `bin/test_cluster_metrics.py`              | validation metrics + tests                                             |
| `assets/test_fixtures/`                                                | fixtures for the metrics tests                                         |
| `validation/`                                                          | acceptance criteria, phase 0 findings, version lock, validation report |
| `db/schema.sql`                                                        | data layer (PHA4GE contextual fields, hAMRonization AMR fields)        |
| `reports/`                                                             | isolate and cluster report templates                                   |
| `docs/fork_plan.md`, `docs/build_guide.md`, `docs/data_staging.md` | plans                                                                  |
