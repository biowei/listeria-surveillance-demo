# Phase 0 — source investigation (milestone M3)

Rule: every finding has its evidence inline (command + output excerpt). Anything you
cannot reproduce from this file does not belong in it.

## 1. Reference genome
- Accession in the Timme sheet (suggested reference): CFSAN023463, SAMN03002783,
  `genBankAssembly` = GCA_001047715.1, run SRR1556288 (`suggestedReference = TRUE`, the only one)
- Observation (2026-10-16): Pathogen Detection PDG000000001.4942 lists this BioSample with
  assembly **GCA_001047715.2**, not .1. Decide which version is the fixed Snippy reference
  and record why; the sheet's `sha256sumAssembly` refers to the version Timme used.
- Downloaded file sha256: TBD — matches sheet? TBD

## 2. cgMLST schema
- Source: **Pasteur cgMLST1748** (BIGSdb `pubmlst_listeria_seqdef`, scheme 3), downloaded
  2026-10-16 with `bin/fetch_bigsdb_scheme.py` (commit 7d86979): 1,748/1,748 loci,
  1,381,390 alleles, headers and ACGT checked per file. Per-locus allele counts and
  sha256: `data/schema/pasteur_cgmlst1748_raw_download.tsv` (not committed; sha256
  `d2621eeeee2b27a94e91e30931b30f7e7836624f39a0eec77e335a5c9ce8fe65`).
  Pasteur is the scheme the 7-allele threshold was calibrated on (`docs/question.md`).
- Published locus count of the Pasteur scheme: **1,748** (2026-10-16:
  `curl -sS https://bigsdb.pasteur.fr/api/db/pubmlst_listeria_seqdef/schemes/3` →
  description `cgMLST1748`, `locus_count` 1748)
- Prepared with `chewBBACA.py PrepExternalSchema` 3.3.10
  (`quay.io/biocontainers/chewbbaca@sha256:7319470168718affb429d4dab8bd78834dd31ceea576917afe4cea3525fe7d95`,
  the version the nf-core `chewbbaca/allelecall` module pins), BSR 0.6 (default),
  translation table 11, **no `--size-filter`**, `--cpu 6`; 10 min. Log: `data/schema_prep.log`.
- Number of loci after preparation: **1,748 / 1,748** (matches the published count).
  Invalid loci: 0. Invalid alleles: 0. Valid alleles: 1,381,390 (all of them).
  Representative alleles: 1,920 (1–12 per locus).
- Prodigal training file used: `Listeria_monocytogenes.trn` bundled with chewBBACA 3.3.10
  (`CHEWBBACA/prodigal_training_files/`), sha256
  `6d5824e9aecf8b72bcf38c70bb9d2a3c11d77a7fb5ffee35d8995f4bc467aced`; copied into the schema.
- Consequence: no locus was lost in preparation, so the 7-allele threshold applies to
  the scheme it was calibrated on. Loci *uncalled* in a given genome (the missing-data
  question in `docs/question.md`) are a separate matter, checked in §3.

## 3. Tool behaviour checks (small synthetic inputs, one behaviour each)
| Check | Input | Expected | Observed | Note |
|---|---|---|---|---|
| chewBBACA missing-data classes → 0 after ExtractCgMLST --t 0 | 2 assemblies, one truncated | missing loci become 0 | TBD | |
| ReporTree treats 0 as missing, not as an allele | toy matrix | distance ignores 0 | TBD | |
| ReporTree partition column naming | toy run | `MST-<t>x1.0`? | TBD | update PARTITION_PATTERN |
| snippy-core: positions with low coverage | — | masked/`-`? | TBD | |

## 4. Staged data
- Timme runs (SENS + SPEC-T), staged 2026-10-16 with `bin/stage_reads.py fetch`
  (commit 250732e):
  `[stage_reads] manifest: 31/31 verified -> data/staging_manifest.tsv`
- Read counts vs ENA catalogue: 31/31 match (`data/staging_manifest.tsv`, `data/ena_catalogue.tsv`)
- md5 vs ENA `fastq_md5`: 31/31 match
- Mate-pairing check (read names R1 = R2): 31/31 pass
- One transient failure: SRR1556288 got an empty ENA filereport on the first pass
  (`expected 1 ENA record, got 0`); the record was returned on re-query and the run
  verified on rerun (1,001,020 read pairs)
- Timme `sha256sumRead1/2` do **not** match the ENA-served files (0/31). ENA serves
  its own gzip of the reads, so the bytes differ from Timme's files. The ENA md5 is the
  integrity check; the Timme sha256 is recorded as information only
- SPEC-A runs: not staged yet
- BioSample collection dates available for: **31 / 31** (`bin/build_metadata.py`, 2026-10-16):
  27 to the day, 4 to the month only (the 4 CDC clinical isolates: 2014-05, 2014-07 ×2,
  2014-08). All 26 outbreak food isolates carry the same date, 2014-07-31, so an epi
  curve of the outbreak arm is one bar plus 2 clinical months. That is a property of
  the public record, not something to smooth over. No date is synthetic yet (SPEC-A
  isolates not added)

## 5. Outbreak typing and SNP clusters before any run (SENS only)
Full commands, checksums and per-isolate table: `data/spec_a_query.md`, Part 1.

- MLST (`staphb/mlst:2.35.0`, scheme `listeria_2`) on three public SENS assemblies
  (GCA_001257525.1, GCA_001257505.1, GCA_001257515.1): all **ST382**, all exact allele
  matches. Pasteur BIGSdb: ST382 → **CC183**, lineage I.
- NCBI Pathogen Detection PDG000000001.4942 places the 28 SENS isolates in **two SNP
  clusters**: PDS000024934 (21) and PDS000024956 (6: CFSAN023466, CFSAN023467,
  MOD1_LS995, MOD1_LS1000, MOD1_LS1005, PNUSAL001024).
- **MOD1_LS994** (SAMN02991381) is not in Pathogen Detection (absent from metadata and
  cluster list). Its reads staged and verified normally.
- Recorded before any pipeline run: NCBI's SNP clustering does not put this
  epidemiologically confirmed outbreak in a single cluster. This says nothing yet about
  cgMLST at the frozen threshold. It is noted here so that the AC3 result cannot be read
  as a surprise in either direction.
