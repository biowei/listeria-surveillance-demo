# Phase 0 — source investigation (milestone M3)

Rule: every finding has its evidence inline (command + output excerpt). Anything you
cannot reproduce from this file does not belong in it.

## 1. Reference genome
- Accession in the Timme sheet (suggested reference): TBD
- Downloaded file sha256: TBD — matches sheet? TBD

## 2. cgMLST schema
- Source (Chewie-NS DownloadSchema or PrepExternalSchema from the Pasteur scheme): TBD
- Number of loci after preparation: TBD (compare with the published locus count)
- Prodigal training file used: TBD

## 3. Tool behaviour checks (small synthetic inputs, one behaviour each)
| Check | Input | Expected | Observed | Note |
|---|---|---|---|---|
| chewBBACA missing-data classes → 0 after ExtractCgMLST --t 0 | 2 assemblies, one truncated | missing loci become 0 | TBD | |
| ReporTree treats 0 as missing, not as an allele | toy matrix | distance ignores 0 | TBD | |
| ReporTree partition column naming | toy run | `MST-<t>x1.0`? | TBD | update PARTITION_PATTERN |
| snippy-core: positions with low coverage | — | masked/`-`? | TBD | |

## 4. Staged data
- Read counts vs ENA catalogue: see `data/staging_manifest.tsv` (all match? TBD)
- md5 vs ENA `fastq_md5`: TBD
- Mate-pairing check (read names R1 = R2): TBD
- BioSample collection dates available for: TBD / 31 (if not all, any epi curve uses dates marked `date_is_synthetic = 1`)
