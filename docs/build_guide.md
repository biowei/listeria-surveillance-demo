# Build guide — Listeria genomic surveillance case study

Prepared 2026-10-08. Source plan: `../13_Cross_Role_Prep/Common_Skills_Plan_29_37_2026-10-08.md`.
Pipeline base: **fork of nf-core/bacass 2.6.0** — see `FORK_PLAN_nfcore_bacass.md` (updated 2026-10-10).
`repo/` is now the flat wiring prototype; its validation, database and report files carry over
(FORK_PLAN §7). Metrics tests are written, with three functions left for you.

**One sentence for the panel, once finished:** *"I built and validated, on public
benchmark data, the chain a microbial genomics service runs every week — reads to
validated clusters to a database to two reports, one for infection control and one
for public health — with the acceptance criteria frozen before the first run."*

---

## How the milestones map to the five skills

| Skill                                                    | Where it is built |
| -------------------------------------------------------- | ----------------- |
| A Genomic surveillance analytics                         | M2, M4, M5        |
| B Epidemiology literacy                                  | M1, M7, M8        |
| C Data integration (SQL, metadata standards, LIMS shape) | M2, M6            |
| D Reporting and teaching                                 | M7, M8            |
| E Evaluation and validation evidence                     | M3, M5            |

Pace: ~1 day per week for 12 weeks. Applications stay first (Cashflow Mode). If a
week is lost to an application, slip the schedule; do not compress M3.

---

## M0 — Set up (week 1, ~3 h)

**Decide compute.** The pipeline needs ~4 cores and ~14 GB RAM for assembly.

| Option                             | Good for                                           | Watch                                                                                                             |
| ---------------------------------- | -------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| Your Mac                           | writing code, stub runs, R reports                 | Apple Silicon: many biocontainers are x86-only, so they run under emulation (slow). Docker Desktop memory ≥ 8 GB |
| GitHub Codespaces (4-core / 16 GB) | the real runs; x86 Linux with Docker               | free monthly quota on personal accounts`[verify current allowance]`; stop the codespace when idle               |
| Seqera Platform + AWS Batch        | the real runs; you already have a case study on it | small AWS cost; same pinned containers                                                                            |

Recommended: ==write and stub-run locally==, real runs on Codespaces or Seqera/AWS.

**Steps** (detail in FORK_PLAN §3)

1. `pip install nf-core`; install Java 17+, Nextflow, Docker.
2. Clone nf-core/bacass at tag `2.6.0` into a new GitHub repo `listeria-surveillance-demo`;
   branch `listeria-surveillance`. Keep the MIT licence and credit bacass.
   (Keep git out of the Cowork folder itself — the folder blocks the deletes git needs.)
3. Baseline: `nextflow run . -profile test,docker --outdir baseline` (Apple Silicon:
   add `emulate_amd64`, or run on Codespaces — not `arm64`: its Wave build of BUSCO fails
   because bioconda has no linux-aarch64 `sepp=4.5.5`; emulated Unicycler is ~4–5× slower).
   Save the MultiQC report.
4. Copy the carry-over files from `repo/` (FORK_PLAN §7).

**Done when:** unmodified bacass test profile passes on your compute; first commit pushed.

---

## M1 — Read and frame the question (weeks 1–2, ~5 h)

Read, with one paragraph of notes each (DOI / first author / year):

1. Timme RE et al., *PeerJ* 2017;5:e3893 — the benchmark design and its truth labels.
2. Mixão V et al., *Genome Medicine* 2023, doi:10.1186/s13073-023-01196-1 — ReporTree:
   clusters at thresholds linked to metadata.
3. Nghiem S et al., *Lancet Reg Health West Pac* 2025;59:101592 — integrated genomic
   surveillance and salmonellosis in Australia (the #37 question).
4. The primary source for the 7-allele *L. monocytogenes* cgMLST threshold — find it
   yourself (start from the Pasteur cgMLST scheme paper) and record it.

Write `docs/question.md` (half a page): the question, the two arms, why the threshold
is a policy choice, what the project will **not** show.

**Done when:** question written; threshold source cited.
**Interview line:** "A cluster threshold is a public-health decision with a
sensitivity cost, not a property of the genome."

---

## M2 — Stage the data (week 2, ~6 h) · skills A, C

1. Download the Timme *Listeria* sheet (31 isolates: 28 outbreak, 3 outgroups).
2. Write the **SPEC-A selection rule** into `acceptance_criteria.md` *before* looking
   for isolates (why: three outgroups give a best-case specificity bound of 0.44 —
   no claim is possible). Run MLST on 2–3 outbreak isolates first to learn the
   clonal complex; then pick ≥ 35 same-CC isolates from NCBI Pathogen Detection in
   different SNP clusters.
3. Write `bin/stage_reads.sh` (or `.py`) following `data/README.md`: ENA catalogue →
   download → md5 → read count → mate-pairing → manifest rebuilt from disk.
4. Build `data/metadata.tsv` from BioSample using PHA4GE minimal field names, plus
   `truth_outbreak` and `dataset_source`. Count how many real collection dates exist.
5. Prepare the cgMLST schema (Chewie-NS `DownloadSchema`, or `PrepExternalSchema` on
   the Pasteur scheme). Record source and locus count.

**Done when:** manifest shows every run verified; metadata complete; schema ready.
**Interview line (#29 criterion 6, honestly):** "I haven't integrated a diagnostic
LIMS, but I designed the data layer a LIMS would hold — contextual fields to the
PHA4GE standard, results keyed to run and commit, and a release step."

---

## M3 — Phase 0 and freeze the criteria (week 3, ~5 h) · skill E

1. Fill `phase0_findings.md`: reference checksum, schema locus count, and the four
   small behaviour checks (each on a toy input — e.g. does ReporTree treat 0 as
   missing?). Fix `PARTITION_PATTERN` in `bin/cluster_metrics.py` from a real toy run.
2. Fill every `TBD` in `acceptance_criteria.md`: QC gates, T, S, AC4–AC5 thresholds.
   Note the table already shows AC3 cannot carry a "lower bound ≥ 0.90" claim at n = 28.
3. Commit and tag `criteria-frozen`.

**Done when:** tag exists; no TBD left.
This is your strongest milestone — it is the RCPAQAP habit applied to your own pipeline.

---

## M4 — Adapt the pipeline (weeks 3–6, ~4 days) · skill A

Follow FORK_PLAN §4–§6:

1. Add a `listeria` profile (`conf/listeria.config`) that selects the short-read path:
   `assembly_type short`, `assembler unicycler`, skip annotation/BUSCO/Kmerfinder, keep
   Kraken2 as a QC gate. No bacass code is removed.
2. `nf-core modules install` mlst, amrfinderplus/run, hamronization/amrfinderplus,
   chewbbaca/allelecall, snippy/run, snippy/core, snpdists, iqtree.
3. Write the two local modules nf-core lacks — `chewbbaca/extractcgmlst` and
   `reportree` — each with a stub and an nf-test.
4. Write `subworkflows/local/population_surveillance` and call it from
   `workflows/bacass.nf` after `ch_assembly` is final.
5. Pin the AMRFinderPlus database, the reference and every container; record them in
   `validation/version_lock.json`; add the commit-gated `run.sh`.
6. Test: `-stub` run (wiring only), then `conf/test_listeria.config` on 3 real isolates.
7. `nf-core pipelines lint`; bacass's own nf-tests still pass.

**Done when:** 3-isolate real run (`-profile test_listeria,docker`) passes end to end;
your nf-tests and bacass's pass; lint clean on your changes; version lock complete.

**Interview line (#29 criteria 3–4):** "I extended an nf-core pipeline with a
population-surveillance subworkflow, wrote two modules nf-core didn't have, and pinned
every tool and database so a rerun is identical."

**Optional, high value:** submit the two local modules to nf-core/modules.

---

## M5 — Run and validate (weeks 6–7, ~2 days) · skills A, E

1. Implement the three functions in `bin/cluster_metrics.py` until
   `python3 bin/test_cluster_metrics.py` prints **all tests passed**.
2. Full run from the pinned commit (~66 isolates).
3. Produce `results/`: `qc_summary.csv`, `typing_check.csv`, `threshold_sweep.csv`
   (`cluster_metrics.py`), `method_agreement.csv` (cgMLST vs SNP), `rerun_check.csv`
   (second run, sha256 of the matrix).
4. Write `VALIDATION_REPORT.md`: one row per AC — pass / fail / not assessable, the
   number, its Wilson bound, the CSV it comes from. Say what was not established.
5. Re-derive every number in the report from its CSV before saving.

**Done when:** every AC has a result traceable to a CSV.
**Interview line (#37 duty):** "I measured how cluster membership moves with the
threshold — the same question as evaluating whether WGS changes cluster detection."

---

## M6 — Data layer (week 8, ~1 day) · skill C

1. Load `results/` into SQLite or DuckDB with `db/schema.sql` (a short Python loader).
2. Convert AMRFinderPlus output with hAMRonization before loading.
3. Write the five exercise queries at the bottom of `schema.sql`; check each against the CSVs.
4. Export one JSON record per isolate (the shape a result message to a LIMS would take).

**Done when:** queries answer correctly; JSON export exists.

---

## M7 — Two reports (weeks 8–9, ~1.5 days) · skills B, D

1. Isolate report (`reports/isolate_report_template.md`) for 3 example isolates —
   clinician / IPC audience, one page, "not assessable" rule.
2. Cluster report (`reports/cluster_summary.Rmd`) with a phylepic chart (CRAN
   phylepic 0.3.0, CIDM-PH's own tool; vignette at cidm-ph.github.io/phylepic).
   If dates are synthetic, say so on the chart and in the first paragraph.
3. Ask a non-bioinformatician to read both and tell you what they would do next.
   Revise once.

**Done when:** both reports render; one outside reader's comments addressed.

---

## M8 — Epidemiology literacy and a teaching piece (weeks 9–10, ~1.5 days) · skills B, D

1. CDC *Principles of Epidemiology in Public Health Practice* (free self-study) —
   lessons on displaying data, surveillance and outbreak investigation `[verify lesson numbers]`.
2. Add a "Discussion" to the validation report: if this ran weekly, what would
   change for timeliness, threshold policy and AMR detection? (No claims about real
   surveillance performance.)
3. Make a 10-slide "Genomics for epidemiologists" deck from your own outputs: what a
   cluster is, why the threshold matters, how to read the phylepic chart, limits.

**Done when:** discussion written; deck exists.
**Interview line (#37 upskilling duty):** "I wrote a short course from my own data
for people who use genomic results but don't produce them."

---

## M9 — Publish and convert to evidence (weeks 11–12, ~1 day)

1. Portfolio page `listeria-surveillance.html` beside the TB reporting demo, labelled
   *public-data demonstration*.
2. GitHub README final; tag `v1.0`.
3. One STAR story in `13_Cross_Role_Prep/STAR_Story_Bank_NSWHP_DPIRD.md`.
4. Resume line (draft, for your approval): *"Portfolio project (public benchmark
   data): built and validated a Listeria genomic surveillance workflow — Nextflow,
   cgMLST/SNP clustering with pre-frozen acceptance criteria, SQL data layer,
   clinician and public-health reports."*
5. Refresh the NSW Health and Queensland criteria answers that this now evidences.

---

## Optional M10 — TB extension (after v1.0)

Add a TB arm: TB-Profiler with the current WHO mutation catalogue, SNP clustering at
commonly used transmission thresholds (source them), and the "not assessable" rule
from your TB demo. TB is named in both #29 (mycobacterial) and #37.

---

## Honest-claim rules for this project

- Always "portfolio project on public data" — never workplace, clinical or
  surveillance experience.
- Synthetic dates are labelled synthetic wherever they appear.
- No RCPAQAP data, no former-employer data, no masked EQA numbers.
- A stub run is never cited as evidence of anything except wiring.

## Working with Claude on this

Bring one milestone per session, e.g. *"M3 — review my acceptance criteria"* or
*"M4 — my CHEWBBACA process fails, here is the log"*. You write the code; I explain,
review and check numbers. Ask me to write a specific piece when you want it.
