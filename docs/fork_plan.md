# Fork plan — adapt nf-core/bacass 2.6.0 for the Listeria surveillance case study

Prepared 2026-10-10. Supersedes the flat `repo/main.nf` prototype for the pipeline
itself; the pipeline-agnostic files in `repo/` carry over (§7).
Checked against: nf-co.re pipeline list (2026-10-10), the bacass 2.6.0 source
(tag `2.6.0`, commit `61b9413`), and nf-core/modules `master` (module inputs and
outputs below were read from source, not from memory).

---

## 1. The choice

| Candidate                    | Status                                                                    | What it does                                                                                                                                                    | Fit                                                                                                                                                                                                                                                                                |
| ---------------------------- | ------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **nf-core/bacass**     | **2.6.0, 2026-05-05**; active                                       | Per-isolate fastp/FastQC → Unicycler (short) → QUAST, Kraken2/Kmerfinder, BUSCO, Prokka/Bakta → MultiQC. 35 nf-core modules, nf-test suite,`arm64` profile | **Chosen.** Covers the first half (QC → assembly → assembly QC) with tested nf-core modules, and has one clean hook — the per-sample `ch_assembly` channel — for a population subworkflow                                                                              |
| nf-core/pathogensurveillance | 1.1.0, 2026-02-13                                                         | Unknown-sample ID by sourmash,**automatic** reference choice, BUSCO multigene + SNP phylogeny (GATK/graphtyper), PIRATE pangenome, HTML report            | Closest in*purpose*, wrong in *design*: auto reference selection and its own docs say it is not for "researchers who would like to extensively test parameters at each stage" — which is what a validation does. No cgMLST, no AMR. Use as a reading reference for its report |
| nf-core/bactmap              | 1.0.0, 2021;`master` README is now a blank template (rewrite under way) | Mapping-based SNP phylogeny                                                                                                                                     | Release is five years old; rewrite unfinished                                                                                                                                                                                                                                      |
| nf-core/pathogenepidemiology | no release; template only (FastQC + MultiQC,*Plasmodium* references)    | —                                                                                                                                                              | Not usable yet; worth watching                                                                                                                                                                                                                                                     |

What the project adds to bacass: MLST, AMR (+ hAMRonization), cgMLST (chewBBACA),
cluster thresholds (ReporTree), reference-based SNPs (Snippy), SNP distances, tree.

## 2. Modules — what exists in nf-core and what you write

| Step                         | Module                          | Source                          | Container (current master)                          |
| ---------------------------- | ------------------------------- | ------------------------------- | --------------------------------------------------- |
| Decompress assembly          | `gunzip`                      | nf-core (already in bacass)     | —                                                  |
| MLST                         | `mlst`                        | nf-core                         | mlst 2.25.0                                         |
| AMR database                 | `amrfinderplus/update`        | nf-core                         | ncbi-amrfinderplus 4.2.7                            |
| AMR                          | `amrfinderplus/run`           | nf-core                         | ncbi-amrfinderplus 4.2.7                            |
| AMR → standard format       | `hamronization/amrfinderplus` | nf-core                         | hamronization 1.1.9                                 |
| cgMLST allele calls          | `chewbbaca/allelecall`        | nf-core                         | chewbbaca 3.3.10                                    |
| cgMLST matrix (missing → 0) | `chewbbaca/extractcgmlst`     | **local — you write it** | chewbbaca (same tag)                                |
| Clusters at thresholds       | `reportree`                   | **local — you write it** | insapathogenomics/reportree (pin v2.6.0)            |
| SNPs vs fixed reference      | `snippy/run`, `snippy/core` | nf-core                         | snippy 4.6.0                                        |
| SNP distances                | `snpdists`                    | nf-core                         | snp-dists 0.8.2                                     |
| Tree                         | `iqtree`                      | nf-core                         | iqtree 3.1.3                                        |
| (M10 TB)                     | `tbprofiler/profile`          | nf-core                         | tb-profiler 3.0.8 — check it is current before use |

The two local modules are small and are good candidates to **contribute upstream to
nf-core/modules** after the project works — a reviewed, public nf-core contribution
is verifiable evidence for #29 criterion 3.

## 3. Set up (replaces M0 steps 1–3)

```bash
pip install nf-core                      # nf-core tools (bacass 2.6.0 was built with 3.5.2)
git clone --branch 2.6.0 https://github.com/nf-core/bacass.git listeria-surveillance-demo
cd listeria-surveillance-demo
git checkout -b listeria-surveillance
# new GitHub repo listeria-surveillance-demo; push this branch there
```

- Keep `LICENSE` (MIT, "The nf-core/bacass team") and credit bacass at the top of
  `README.md` and in `CITATIONS.md`: *"Built on nf-core/bacass 2.6.0."*
- **Baseline before any change:** `nextflow run . -profile test,docker --outdir baseline`
  (on Apple Silicon: `-profile test,arm64,docker`, or run on Codespaces). Save the
  MultiQC report. If the unmodified pipeline does not pass here, fix the environment
  first — never debug your changes and your setup at the same time.

## 4. Select the short-read path with a dedicated profile (no code removal)

Nothing is deleted from bacass. The long-read and hybrid branches only run when their
params ask for them, so a profile that sets the short-read params is enough — the same
pattern bacass's own `conf/test.config` uses.

Create `conf/listeria.config` and register it in `nextflow.config`:

```groovy
// nextflow.config → profiles { ... }
listeria      { includeConfig 'conf/listeria.config' }
test_listeria { includeConfig 'conf/test_listeria.config' }   // 3-isolate test, §8
```

```groovy
// conf/listeria.config
params {
    config_profile_name        = 'Listeria surveillance case study'
    config_profile_description = 'Short-read assembly + population surveillance (public benchmark data)'
    assembly_type   = 'short'      // Illumina only
    assembler       = 'unicycler'  // bacass's tested short-read path
    skip_annotation = true         // chewBBACA does its own gene prediction
    skip_busco      = true         // QUAST + cgMLST loci called cover completeness
    skip_kmerfinder = true         // keep one species check
    skip_kraken2    = false        // species/contamination QC gate (AC1); set kraken2db, record it in version_lock.json
}
```

Run with `-profile listeria,docker`. Your new params (`reference`, `schema_dir`,
`metadata`, `amrfinder_db`) still need a `null` default in `nextflow.config` and an
entry in `nextflow_schema.json` (`nf-core pipelines schema build`), because nf-schema
validates every param the pipeline uses. Their *values* go in the profile or a
`-params-file`, not in the defaults.

Why this rather than trimming:

- your diff against bacass stays small — reviewers see exactly what you added;
- bacass's own nf-tests keep passing, which proves your additions did not break it;
- you can still pull later bacass releases into the fork;
- less work and less risk than removing branches, modules, schema entries and tests.

Removing the unused branches is **optional polish**, not part of the project.

## 5. Add the population subworkflow

```bash
nf-core modules install mlst
nf-core modules install amrfinderplus/update
nf-core modules install amrfinderplus/run
nf-core modules install hamronization/amrfinderplus
nf-core modules install chewbbaca/allelecall
nf-core modules install snippy/run
nf-core modules install snippy/core
nf-core modules install snpdists
nf-core modules install iqtree
nf-core modules create chewbbaca/extractcgmlst     # → modules/local/
nf-core modules create reportree                   # → modules/local/
nf-core subworkflows create population_surveillance  # → subworkflows/local/
```

Wiring sketch for `subworkflows/local/population_surveillance/main.nf` (interfaces
checked against module source 2026-10-10; you write and test it):

```nextflow
take:
ch_assembly    // [ meta, scaffolds.fa.gz ]  from bacass ch_assembly (Unicycler output is gzipped)
ch_reads       // [ meta, [ r1, r2 ] ]       from bacass ch_short_preprocessed (trimmed)
reference      // path  — the Timme suggested reference, FIXED (never auto-selected)
schema         // path  — chewBBACA schema directory
metadata       // path  — PHA4GE-style TSV with truth_outbreak
amrfinder_db   // path  — a PINNED amrfinderdb.tar.gz (see §6)

main:
// 1  decompress:   branch on '.gz' → GUNZIP (include as GUNZIP_ASSEMBLY) → ch_fasta [meta, fasta]
// 2  MLST(ch_fasta)
// 3  AMRFINDERPLUS_RUN(ch_fasta, amrfinder_db)
//    HAMRONIZATION_AMRFINDERPLUS(AMRFINDERPLUS_RUN.out.report, 'tsv',
//        AMRFINDERPLUS_RUN.out.tool_version.first(), AMRFINDERPLUS_RUN.out.db_version.first())
// 4  cohort: ch_fasta.map{ m, f -> f }.collect().map{ fs -> [[id:'cohort'], fs] }
//    CHEWBBACA_ALLELECALL(ch_cohort, [[id:'schema'], schema])   // emits .alleles [meta, *_results_alleles.tsv]
//    CHEWBBACA_EXTRACTCGMLST(CHEWBBACA_ALLELECALL.out.alleles)   // local: ExtractCgMLST --t 0
//    REPORTREE(CHEWBBACA_EXTRACTCGMLST.out.matrix, metadata)     // local: -thr via ext.args in conf/modules.config
// 5  SNIPPY_RUN(ch_reads, reference)                              // uses meta.single_end (bacass sets it)
//    join .vcf and .aligned_fa by meta, collect → [[id:'cohort'], [vcfs], [aligned_fas]]
//    SNIPPY_CORE(ch_core_in, reference)                           // emits .aln
//    SNPDISTS(SNIPPY_CORE.out.aln)
//    IQTREE(SNIPPY_CORE.out.aln.map{ m, a -> [m, a, []] }, [], [], [], [], [], [], [], [], [], [], [], [])
//                                                                 // 12 optional path inputs after the tuple

emit:
// mlst, amr (hAMRonization tsv), cgmlst matrix, partitions, snp_dists, tree
```

Hook in `workflows/bacass.nf`: include the subworkflow and call it after the
assembly section (after `ch_assembly` is final, before annotation). Add the new
params to `nextflow.config` and `nextflow_schema.json`; put tool arguments
(`ext.args`, `ext.prefix`, `publishDir`) in `conf/modules.config`, not in the modules.

Tool versions: bacass 2.6.0 and current modules both report versions through the
`versions` topic channel, so newly installed modules fit without extra `ch_versions` plumbing.

## 6. Reproducibility decisions (your validation protocol applies)

- **Do not run `AMRFINDERPLUS_UPDATE` in validation runs.** It fetches the latest
  database each time, so AC7 (identical rerun) would fail by design. Run it once,
  keep the tarball, pass it with `--amrfinder_db`, record its version.
- **Fixed reference** for Snippy (Timme `suggestedReference`), checksum in `phase0_findings.md`.
- **chewBBACA `--no-inferred`** via `ext.args` so a run cannot change the schema.
- Pin ReporTree to an exact tag (v2.6.0, by digest; no v2.6.1 was released), never `latest`.
- Gate the run on the commit (`run.sh` checks `git rev-parse HEAD` vs `version_lock.json`).
- `-stub` still works: every nf-core module ships a stub, and your two local modules
  must too. A stub run proves wiring only.

## 7. Carry over from the prototype `repo/`

| From`repo/`                                                                | To the fork               | Note                                                                                        |
| ---------------------------------------------------------------------------- | ------------------------- | ------------------------------------------------------------------------------------------- |
| `bin/cluster_metrics.py`, `bin/test_cluster_metrics.py`                  | `bin/`                  | bacass already has`bin/`; scripts there are on `PATH` inside processes                  |
| `tests/fixtures/partitions_toy.tsv`                                        | `assets/test_fixtures/` | keep apart from nf-test's`tests/`                                                         |
| `acceptance_criteria.md`, `phase0_findings.md`, `version_lock.json`    | `validation/`           | unchanged                                                                                   |
| `db/schema.sql`                                                            | `db/`                   | unchanged                                                                                   |
| `reports/`                                                                 | `reports/`              | unchanged                                                                                   |
| `data/README.md`                                                           | `docs/data_staging.md`  | unchanged                                                                                   |
| `main.nf`, `nextflow.config`, `conf/stub.config`, `tests/stub_data/` | **retire**          | replaced by bacass structure; keep in the workstation as the record of the wiring prototype |

## 8. Tests

- Your own test profile `conf/test_listeria.config`: 3 isolates (2 outbreak, 1
  outgroup), reads subsampled, a cut-down schema if run time demands it.
- nf-test: one pipeline-level test (`tests/listeria.nf.test`) plus module tests for
  the two local modules (`nf-core modules test reportree`).
- Keep bacass's own nf-tests passing — they show your additions left the original paths intact.

## 9. Milestone changes in BUILD_GUIDE

- **M0** — §3 here (clone bacass, baseline test run).
- **M4** — §4–§6 here: `listeria` profile, install modules, write the two local modules
  and the subworkflow, nf-tests, version lock.
- M1–M3 and M5–M9 unchanged.
