# question.md

Oct 13, 2026 · @Chris

*This is a portfolio project on public benchmark data. It is not a clinical or public-health service and not a validation of any laboratory's method.*

## The question

Given only sequencing reads, does the **pipeline** place all 28 isolates of a known *Listeria monocytogenes* outbreak in one cluster at ≤ 7 cgMLST allelic differences, and keep unrelated isolates of the same clonal complex out of it? The answer matters to two readers: infection control, who need to know whether a patient's isolate belongs to a cluster, and public health, who need to know whether the cluster is real before investigating a food source. Pass marks are set in `validation/acceptance_criteria.md`, not here.

## Two questions, three test sets

Sensitivity asks whether the pipeline finds the outbreak; specificity asks whether it leaves unrelated isolates out. Each test set measures one of them.

| Test set | Tests | Isolates | n | Truth source | What it can bear |
| --- | --- | --- | --- | --- | --- |
| SENS | Sensitivity | Outbreak isolates, 2014 US stone-fruit listeriosis outbreak (Timme sheet `1408MLGX6-3WGS`) | 28 | Timme 2017, epidemiologically confirmed | 28/28 gives a Wilson 95% lower bound of 0.879 at best |
| SPEC-T | Specificity | Outgroups in the same sheet | 3 | Timme 2017 | 3/3 gives a lower bound of 0.439: no specificity claim on its own |
| SPEC-A | Specificity | Same clonal complex (CC183), NCBI Pathogen Detection, different SNP cluster | 5 (the rule asked for 40; only 5 CC183 SNP clusters exist) | Unrelatedness **assumed** from a different SNP cluster, not shown epidemiologically | With SPEC-T, 8/8 gives a lower bound of 0.676: a check for counterexamples, not a specificity claim |

SPEC-A isolates come from the same clonal complex because isolates from other complexes usually differ by 1,000 or more alleles (Moura 2016) and test nothing. The selection rule for SPEC-A was written into the acceptance criteria before any isolate was looked at (M2). It found only 5 eligible isolates, 4 of them the outbreak's own ST382, so the specificity test is hard but small.

## Why the threshold is a policy choice

The 7-allele cutoff is a judgement fitted to one collection of isolates, not a property of the genome. Moura et al. (2016) compared pairs of isolates from the same outbreak with pairs with no known link. Most outbreak pairs differed by 7 alleles or fewer, most unlinked pairs by more than 10, and few fell between. A clustering score (Dunn's index) peaked at 7.3, so they defined a cgMLST type as profiles within 7 mismatches of at least one other member.

Moving the cutoff trades one error for another. Raise it and more true cases join the cluster, but so do unrelated ones, which costs case interviews and food sampling. Lower it and clusters are tighter, but a long-running source drifts by about 0.2–0.3 alleles a year and can split across the line. Which error costs more is for a public-health body to decide, not the pipeline.

Three conditions travel with the number:

- **The scheme.** The 7 was calibrated on the Pasteur scheme of 1,748 loci. With another schema the number has no direct justification; the schema chosen in M2 is recorded and this sentence revised.
- **Missing data.** Moura measures distance as the proportion of mismatched loci among those called in both profiles, so the cutoff is really 0.400% (7 of 1,748); when loci are uncalled, the allowed number of mismatches falls below 7. Whether ReporTree uses counts or proportions, and how it treats uncalled alleles, is checked in Phase 0 (M3).
- **Single linkage.** An isolate joins a cluster by being within 7 of any one member, so a cluster can chain together isolates that are far apart.

Because the threshold is a choice, M5 reports results across a range of thresholds as well as at 7.

## What this project will not show

Recovering one known outbreak shows the pipeline can do it once, on this data. It will not show:

- that the pipeline works on other outbreaks, clonal complexes, sequencers or laboratories
- prospective performance: the answer was known before the run
- specificity: 8 non-outbreak isolates cannot establish it (best-case lower bound 0.676), and even those rest on the assumption that SPEC-A isolates are unrelated
- high certainty: even 28/28 leaves the lower bound at 0.879
- that 7 alleles is the right threshold; the project uses it, it does not validate it
- anything about time trends where collection dates are synthetic (flagged on every chart)
- fitness for clinical or public-health use

## References

1. Timme RE et al. Benchmark datasets for phylogenomic pipeline validation. *PeerJ* 2017;5:e3893. [doi:10.7717/peerj.3893](https://doi.org/10.7717/peerj.3893)
2. Jackson BR et al. Listeriosis associated with stone fruit — United States, 2014. *MMWR* 2015;64(10):282–3. [PMID 25789745](https://pubmed.ncbi.nlm.nih.gov/25789745/)
3. Moura A et al. Whole genome-based population biology and epidemiological surveillance of *Listeria monocytogenes*. *Nat Microbiol* 2016;2:16185. [doi:10.1038/nmicrobiol.2016.185](https://doi.org/10.1038/nmicrobiol.2016.185)
4. Mixão V et al. ReporTree. *Genome Med* 2023;15:43. [doi:10.1186/s13073-023-01196-1](https://doi.org/10.1186/s13073-023-01196-1)
5. Nghiem S et al. Integrated genomic surveillance and non-typhoidal *Salmonella* in Australia. *Lancet Reg Health West Pac* 2025;59:101592. [doi:10.1016/j.lanwpc.2025.101592](https://doi.org/10.1016/j.lanwpc.2025.101592)

Sources checked against PubMed and the Timme GitHub sheet on 2026-10-12.
