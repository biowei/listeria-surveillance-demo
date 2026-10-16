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

Rule commit: d5f3561 (steps 4–5 as amended); script `bin/select_spec_a.py` at 20488a7.

History before the final rule (2026-10-16): the first executable version of the rule
(commit e848d50) walked the 17,638 step-3 survivors one at a time and typed each one.
It was stopped after 13 isolates (~36 s each; a full walk was estimated at ~7 days).
Those 13 typed as CC1, CC3, CC6, CC7, CC14, CC87 and CC89, none CC183. No CC183
candidate had been viewed when steps 4–5 were amended to type one isolate per cluster.

### Run of 2026-10-16 (snapshot PDG000000001.4942)

Filters applied, in rule order, with the count left after each:

| Step | Kept |
|---|---|
| BioSamples in snapshot | 85,527 |
| not in the Timme sheet | 85,497 |
| in a SNP cluster | 73,153 |
| not in PDS000024934 / PDS000024956 | 72,410 |
| collection year 2010–2016 | 21,822 |
| `asm_acc` and an SRA run present | 17,638 (in 2,674 SNP clusters) |
| excluded: BioSample in two SNP clusters (no rule covers it) | 1 (SAMEA104485064) |
| step 4: clusters with a CC | 2,661; 13 excluded (no exact ST in 3 tries) |
| step 4: **CC183 clusters** | **5** |
| step 5: selected | **5** (3 skipped as cluster already taken; 0 failed the 5c confirmation) |

Per-cluster and per-isolate evidence: `data/spec_a_clusters.tsv`, `data/spec_a_selection.tsv`.

Selected (BioSample, run, PDS, ST):

| BioSample | Run | PDS | ST |
|---|---|---|---|
| SAMN13910650 | SRR10958856 | PDS000055841 | 382 |
| SAMN13910668 | SRR10958900 | PDS000070289 | 382 |
| SAMN14163152 | SRR11144656 | PDS000058433 | 2126 |
| SAMN14164734 | SRR11146857 | PDS000058447 | 382 |
| SAMN19761656 | SRR14850044 | PDS000237798 | 382 |

**Outcome: SHORTFALL, 5 of 40** (rule step 6: stop and report, widen nothing). Not yet
appended to `data/runs.tsv`; what to do with the shortfall is an amendment decision.
4 of the 5 are ST382, the outbreak's own ST, in SNP clusters different from the outbreak's.

Replacements (isolate, reason, replacement): none yet
