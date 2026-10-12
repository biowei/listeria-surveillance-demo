# Isolate genomic report — DEMONSTRATION (public data, not a patient report)

Audience: a clinician or an infection prevention & control nurse. One page.
Rule carried from the TB reporting demo: if a result cannot be assessed (QC fail,
low coverage at the relevant locus), say **"not assessable"** — never default to
"not detected".

| Field | Value |
|---|---|
| Isolate ID | {{isolate_id}} |
| Organism (confirmed by) | *Listeria monocytogenes* ({{species_method}}) |
| Sequence quality | {{PASS / FAIL — reason}} |
| Sequence type / clonal complex | ST{{st}} / CC{{cc}} |
| Cluster status | {{"Part of cluster <name> (<n> isolates within <T> alleles)" / "No close match in this dataset"}} |
| Acquired resistance genes | {{list, or "none detected" only when QC passed}} |

**What this means:** {{one or two plain sentences}}

**What this does not tell you:** {{e.g. genomic relatedness supports, but does not
prove, a common source; epidemiological investigation decides}}

Pipeline {{commit}} · run {{run_id}} · reviewed by {{reviewer}} · released {{date}}
