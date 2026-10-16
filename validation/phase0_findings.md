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
Run 2026-10-16. Containers: chewBBACA 3.3.10 (`sha256:73194701…7fe4cea3525fe7d95`),
ReporTree **v2.6.0** (`insapathogenomics/reportree@sha256:061a2538173c7419a58d429186f239aac235735d701b2390b882a5d8738fe23f`),
snippy 4.6.0 (`quay.io/biocontainers/snippy@sha256:8d1589ab60af6a9dac53dd069b71fdffc2d6530047e4b9742b59a89fbe2a5b70`,
the nf-core `snippy/run` and `snippy/core` pin).

| Check | Input | Expected | Observed | Note |
|---|---|---|---|---|
| chewBBACA missing-data classes → 0 after ExtractCgMLST --t 0 | 2 assemblies, one truncated | missing loci become 0 | **Yes**: LNF, ASM, ALM, NIPH → `0`. But `INF-x` → `x` | inferred alleles are kept, see 3a |
| ReporTree treats 0 as missing, not as an allele | toy matrix | distance ignores 0 | **Yes**, and distance is a **count**, not a proportion | see 3b; matters for the 7-allele threshold |
| ReporTree partition column naming | toy run | `MST-<t>x1.0`? | **`MST-<t>x1.0`** (grapetree); `single-<t>x1.0` (HC). Partitions file's sample column is **`sequence`** | `PARTITION_PATTERN` matches grapetree; see 3c |
| snippy-core: positions with low coverage | real reads at full and ~4% depth vs a 100 kb reference | masked/`-`? | `N` below min. coverage, `-` at zero coverage, `n` for mixed; all dropped from `core.aln` | see 3d |

### 3a. chewBBACA AlleleCall + ExtractCgMLST
Input: GCA_001257525.1 (`full`, 2,916,995 bp, 36 contigs) and its first 1,458,497 bp (`half`).

```
chewBBACA.py AlleleCall -i genomes -g <schema copy> -o ac --no-inferred --cpu 6
chewBBACA.py ExtractCgMLST -i ac/results_alleles.tsv -o cg --t 0
results_statistics.tsv:  full  EXC 1651  INF 86  NIPH 7  ALM 1  ASM 2  LNF 1
                         half  EXC 899   INF 2   ALM 1  ASM 1  LNF 845
cgMLST0.tsv: 1,748 loci; full 11 zeros, half 847 zeros
class → cgMLST0 value (half): LNF→0 (845), ALM→0, ASM→0, INF-716→716, INF-881→881
```

- Missing classes become `0` as expected.
- **`--no-inferred` stops the schema from growing, but inferred alleles still appear in the
  results.** `INF-x` becomes the integer `x` in `cgMLST0.tsv`. Within one run the IDs are
  consistent: 45 novel alleles were `INF-x` in `full` and the plain `x` in `half`, the same
  allele. The IDs are not stable across runs with different isolates, so matrices from
  different runs must not be merged. AC7 compares two runs with identical inputs, which
  is fine.
- **AlleleCall writes into the schema directory on first use, even with `--no-inferred`**:
  `loci_modes` and `pre_computed/` (14 files), plus a file in `short/`. With a read-only
  mount it fails (`OSError: [Errno 30] Read-only file system: '/schema/loci_modes'`).
  Nextflow stages inputs as symlinks, so a pipeline run would modify the canonical schema.
  **Resolved in M4 (2026-10-16):** `bin/precompute_schema.sh` ran AlleleCall once
  (read-write), then again on a read-only mount: the second call succeeded and the tree
  checksum stayed `5e961048…71e4a0`. Pipeline runs use the pre-computed schema.
- 2 loci were NIPH in `full` and exact in `half` (the second copy of a paralogue was in
  the removed half).

### 3b. ReporTree: missing data and distance
Toy matrix, 6 loci (`0` = missing):

```
S1 1 1 1 1 1 1 | S2 1 1 1 1 1 2 | S3 0 0 1 1 1 1 | S4 2 2 2 2 2 2 | S5 1 1 1 1 2 2
reportree.py -a matrix.tsv -m meta.tsv --analysis grapetree --method MSTreeV2 -thr 0-3 -out gt
→ partitioning_grapetree.py ... --missing 0 --site-inclusion 0.0 --loci-called 0.0 --missing-code 0
gt_dist_hamming.tsv: S1–S3 0, S3–S4 4, S1–S4 6
MST-0x1.0: S1 + S3 cluster_1; S2, S5, S4 singletons
MST-1x1.0: S1, S2, S3, S5 cluster_1 (S5 joins through S2: single linkage); S4 singleton
```

- `0` is treated as missing: S1–S3 = 0. It would be 2 if `0` were an allele.
- **The distance is the number of differing loci among loci called in both, not
  scaled.** S3–S4 = 4 (4 shared loci), not 6. Moura 2016 defines the threshold on the
  *proportion* (7/1,748 = 0.400 %). Under a count, a profile with uncalled loci looks
  closer than it would under Moura's proportion. The difference is small when nearly all
  loci are called, and grows with missing data. AC1's loci-called gate is what keeps it
  small; this belongs with the T decision in M3.
- Default filters are off (`--site-inclusion 0.0`, `--loci-called 0.0`): no locus or
  sample is dropped unless set.
- MSTreeV2's own matrix (`gt_dist_grapetree.tsv`) is asymmetric where data are missing
  (S3→S1 2.0, S1→S3 0.0). Partitions follow the MST; cite `gt_dist_hamming.tsv` for
  pairwise counts.

### 3c. ReporTree partition naming
`gt_partitions.tsv` header: `sequence  MST-0x1.0  MST-1x1.0  MST-2x1.0  MST-3x1.0`
(HC: `single-0x1.0 …`). `PARTITION_PATTERN = r"^MST-(\d+)x"` matches grapetree output.
The sample column is **`sequence`** in `*_partitions.tsv`, but `sample` in
`*_metadata_w_partitions.tsv`. `sweep()`'s default `sample_col="sample"` only fits the
second file.

### 3d. snippy / snippy-core
Reference: first 100 kb of contig LHSD01000001.1 (GCA_001257525.1). Reads: SRR1553826
(the same isolate), full depth, and `seqtk sample -s 11 … 0.04`.

```
core.txt   ID    ALIGNED  UNALIGNED  HET  LOWCOV
           full  99793    0          207  0
           low   5506     2656       32   91806
core.full.aln characters: full  ACGT 99,793  n 207
                          low   ACGT 5,506   N 91,806   - 2,656   n 32
snippy-core → "snp-sites -c -o core.aln core.full.aln ... No SNPs were detected"; exit 2
```

- Below minimum coverage (snippy default 10×) → `N`; zero coverage → `-`; mixed → `n`.
- `snp-sites -c` keeps only columns that are A/C/G/T in **every** sample. **One
  low-coverage isolate shrinks the core for all isolates.** AC1's depth gate protects
  the SNP arm as well as the assembly.
- **snippy-core exits 2 when there are no variant sites.** A test profile of 3 near-
  identical outbreak isolates could hit this. **Resolved in M4 (2026-10-16):** the
  nf-core `snippy/core` module is patched (`snippy-core.diff`) to write a zero-length
  core alignment only on the "No SNPs were detected" failure. Tested on this §3d data:
  the no-SNP pair passes (snp-dists 0.8.2 gives all-zero distances); a pair with 5
  introduced differences gives a 5-column core.aln as before; a genuine snippy-core
  error (sample/reference contig mismatch) still fails the task.

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
- Raw read depth of the SENS isolates (pre-run input, before trimming; 2026-10-16):
  read pairs × 2 × mean read length of the first 1,000 reads per mate ÷ 2.95 Mb, from
  `data/staging_manifest.tsv` and `data/fastq/`.
  PDS000024956 (6): CFSAN023466 28×, CFSAN023467 34×, PNUSAL001024 104×, MOD1_LS1005 121×,
  MOD1_LS1000 141×, MOD1_LS995 256×. PDS000024934 (21): min 34×, median 150×, max 260×.
  MOD1_LS994 (not in PD): 124×. Lowest SENS: CFSAN023466 28×, CFSAN023467 34×, CFSAN023468 34×.
  - Hypothesis considered: low depth explains the outbreak's split across two SNP clusters.
    **Not supported as a general explanation.** 4 of the 6 in PDS000024956 have
    104–256×, and CFSAN023468 (34×) is in PDS000024934. At most it may contribute for
    CFSAN023466 and CFSAN023467. Recorded before any run. Not used to choose S or the
    AC1 depth gate.
  - Consequence for AC1: CFSAN023466 is a SENS isolate at 28× raw. A depth gate between
    28× and the post-trim depth could remove it before the run, making AC3 27/28
    assessable. The gate is set from its source, not from this list.
- Prior expectation from the literature (recorded 2026-10-16, before any run): Chen Y
  et al. *Appl Environ Microbiol* 2016;82:7030–40 (doi:10.1128/AEM.01486-16) studied this
  outbreak (2014 stone fruit; R. Timme co-author). Outbreak-associated isolates were
  serotype IVb-v1, all ST382, and differed by up to 42 SNPs (CFSAN SNP pipeline). A
  separate serotype 1/2b, CC5 cluster (up to 17 SNPs) came from the fruit and packing
  environment. Consequences: a single-linkage S = 20 may or may not hold all 28 SENS
  isolates together. AC2 will show whether any of the 28 is not ST382. This
  expectation was not used to choose S.
