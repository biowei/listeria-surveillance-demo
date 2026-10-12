# Data staging (milestone M2)

Nothing in this folder is committed except this README, the samplesheet, the
metadata table and the staging manifest. FASTQ and the schema stay local.

## 1. Benchmark isolates (SENS + SPEC-T arms)
Source: https://github.com/WGS-standards-and-analysis/datasets — the
*L. monocytogenes* stone-fruit sheet (31 isolates: 28 outbreak, 3 outgroups;
file name `[verify]` in the repo's datasets folder). Columns used:
`biosample_acc`, `strain`, `SRArun_acc`, `outbreak`, `suggestedReference`.

## 2. Added non-outbreak isolates (SPEC-A arm)
Write the selection rule into `acceptance_criteria.md` FIRST, then pick isolates
from NCBI Pathogen Detection by that rule. Record PDS cluster IDs.

## 3. Fetch and verify (per run accession)
Catalogue (read counts and md5 come from here, never from memory):

    https://www.ebi.ac.uk/ena/portal/api/filereport?accession=<SRR>&result=read_run&fields=run_accession,read_count,fastq_ftp,fastq_md5&format=tsv

For every run:
1. download both mates from `fastq_ftp`;
2. md5 matches `fastq_md5`;
3. read count of R1 and of R2 equals `read_count` (count lines/4 after gunzip;
   require lines > 0 and lines % 4 == 0);
4. read names in R1 and R2 match (strip `/1` `/2` and comments) — on mismatch,
   delete BOTH files so a resume refetches them;
5. at the end, rebuild `staging_manifest.tsv` from the files on disk and exit
   non-zero if any run is missing.

## 4. Contextual metadata
Pull BioSample attributes (collection date, location, source) for every isolate
into `metadata.tsv` using PHA4GE minimal field names. Where a date is not
public, leave it empty or mark `date_is_synthetic = 1` if you fill it for the demo.
