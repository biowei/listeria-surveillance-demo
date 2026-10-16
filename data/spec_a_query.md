# SPEC-A query record

Evidence for the SPEC-A selection rule in `validation/acceptance_criteria.md`.
Part 1 holds the lookups that fill the rule's placeholders. They use SENS isolates
only, and no SPEC-A candidate was viewed. Part 2 is filled only after the commit that
completes the rule.

## Part 1 — SENS-only lookups (2026-10-16)

### 1a. Clonal complex of the outbreak strain

MLST ran on three public GenBank **assemblies** of SENS isolates (listed in the Timme
sheet), not on our reads. AC2 retypes every isolate from reads later.

| Strain | Assembly | File sha256 |
|---|---|---|
| MOD1_LS1004 | GCA_001257525.1 | `67123a20aa37b050487a286ea995898099e481947f1dd0febe64ae02983da186` |
| MOD1_LS1010 | GCA_001257505.1 | `f3b9a96cb3f98c4a052b2bd2ccc9134108dc4f702f4ccb3674e924e66affdd08` |
| MOD1_LS996 | GCA_001257515.1 | `25df76652a8cb3eceff48f18a075dd5d9c29a2eb0db44eb85b429c5a7d6971af` |

```bash
curl -sSfL -o GCA_001257525.1.zip "https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession/GCA_001257525.1/download?include_annotation_type=GENOME_FASTA"
# (same for GCA_001257505.1 and GCA_001257515.1, then unzip)
docker run --rm --platform linux/amd64 -v "$PWD":/data -w /data staphb/mlst:2.35.0 \
  mlst --scheme listeria_2 $(find . -name "*.fna")
```

Container: `staphb/mlst@sha256:d11a9ea089158c8648852f44ea7de495ea60001acb9850127b73b904e7c73642`
(mlst 2.35.0).

Result: all three isolates are **ST382**. Every allele is an exact match: abcZ 1, bglA 51, cat 11, dapE 13,
dat 2, ldh 5, lhkA 5.

ST → CC from the Pasteur BIGSdb REST API (database `pubmlst_listeria_seqdef`, scheme 2 = MLST):

```bash
curl -sS https://bigsdb.pasteur.fr/api/db/pubmlst_listeria_seqdef/schemes/2/profiles/382
# → "ST": 382, "CC": "CC183", "Lineage": "I"
```

**CC = CC183** (lineage I). The three isolates agree, so the rule's stop condition is not triggered.

### 1b. SNP cluster(s) of the outbreak

NCBI Pathogen Detection snapshot **PDG000000001.4942** (`latest_snps` on 2026-10-16).

| File | sha256 |
|---|---|
| `Metadata/PDG000000001.4942.metadata.tsv` | `2a9e6fa03e99d7957aeba378d83ed1ebcd12a59e12bf30247f605760deae22d5` |
| `Clusters/PDG000000001.4942.reference_target.cluster_list.tsv` | `30a3776e1df5a42b271998363a11ae03b9383fab4fc58eee688047e8158af5a0` |

The cluster list covers every *Listeria* isolate, so it was filtered in the shell to the
28 SENS BioSamples (`arm == SENS` in `data/runs.tsv`). No other rows were printed or opened.

```bash
B=https://ftp.ncbi.nlm.nih.gov/pathogen/Results/Listeria/latest_snps
curl -sSfO $B/Clusters/PDG000000001.4942.reference_target.cluster_list.tsv
awk -F'\t' 'NR>1 && $4=="SENS"{print $3}' data/runs.tsv > sens_biosamples.txt
awk -F'\t' 'NR==FNR{want[$1];next} FNR==1{next} ($3 in want){print $3"\t"$2"\t"$1}' \
  sens_biosamples.txt PDG000000001.4942.reference_target.cluster_list.tsv | sort -u
```

Result (27 of the 28 SENS BioSamples are found; some have two PD targets, and both
targets always fall in the same cluster):

| PDS (version in this snapshot) | SENS isolates |
|---|---|
| PDS000024934 (.216) | 21 — CFSAN023463, CFSAN023464, CFSAN023465, CFSAN023468, CFSAN023469, CFSAN023470, CFSAN023471, MOD1_LS982, MOD1_LS985, MOD1_LS989, MOD1_LS996, MOD1_LS997, MOD1_LS998, MOD1_LS1003, MOD1_LS1004, MOD1_LS1006, MOD1_LS1008, MOD1_LS1009, MOD1_LS1010, MOD1_LS1011, PNUSAL000870 |
| PDS000024956 (.5) | 6 — CFSAN023466, CFSAN023467, MOD1_LS995, MOD1_LS1000, MOD1_LS1005, PNUSAL001024 |
| not in Pathogen Detection | 1 — MOD1_LS994 (SAMN02991381), absent from both metadata and cluster list |

**SNP clusters to exclude: PDS000024934 and PDS000024956.** PDS version suffixes change
with every snapshot, so the rule cites the accession without its version.

## Part 2 — candidate query (after the rule is complete and committed)

Rule commit: TBD
Filters applied, in rule order, with the count left after each: TBD
Selected 40 (BioSample, run, PDS): TBD → appended to `data/runs.tsv` as `arm = SPEC-A`
Replacements (isolate, reason, replacement): none yet
