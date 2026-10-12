-- listeria-surveillance-demo — data layer (milestone M6). SQLite / DuckDB compatible.
--
-- Purpose: practise the shape of a LIMS / surveillance-database interface —
-- every result is tied to an isolate, a pipeline run (commit) and a release
-- decision. Contextual fields follow the PHA4GE minimal pathogen-agnostic
-- contextual data specification (field names adapted to snake_case).
--
-- LABEL: public data; truth_outbreak exists for validation only and would never
-- sit in an operational table.

CREATE TABLE pipeline_run (
    run_id            TEXT PRIMARY KEY,       -- Nextflow run name or UUID
    pipeline_commit   TEXT NOT NULL,          -- git SHA the run was gated on
    nextflow_version  TEXT NOT NULL,
    started_at        TEXT NOT NULL,          -- ISO 8601
    params_json       TEXT                    -- copy of params used
);

CREATE TABLE isolate (
    isolate_id                     TEXT PRIMARY KEY,   -- specimen_collector_sample_id
    biosample_accession            TEXT,
    sra_run_accession              TEXT,
    organism                       TEXT NOT NULL,
    sample_collection_date         TEXT,               -- ISO 8601; NULL if not public
    date_is_synthetic              INTEGER NOT NULL DEFAULT 0 CHECK (date_is_synthetic IN (0, 1)),
    geo_loc_name_country           TEXT,
    geo_loc_name_state             TEXT,
    sample_collected_by            TEXT,
    sequenced_by                   TEXT,
    purpose_of_sampling            TEXT,
    purpose_of_sequencing          TEXT,
    data_custodian_organization    TEXT,
    dataset_source                 TEXT NOT NULL,      -- 'Timme2017_Lm' | 'NCBI_PD_added'
    truth_outbreak                 INTEGER CHECK (truth_outbreak IN (0, 1))  -- validation only
);

CREATE TABLE qc_result (
    isolate_id      TEXT NOT NULL REFERENCES isolate(isolate_id),
    run_id          TEXT NOT NULL REFERENCES pipeline_run(run_id),
    reads_after_trim INTEGER,
    q30_rate        REAL,
    est_depth       REAL,
    total_length    INTEGER,
    n_contigs       INTEGER,
    n50             INTEGER,
    gc_percent      REAL,
    cgmlst_loci_called_pct REAL,
    qc_pass         INTEGER NOT NULL CHECK (qc_pass IN (0, 1)),
    qc_fail_reason  TEXT,                -- required when qc_pass = 0
    PRIMARY KEY (isolate_id, run_id)
);

CREATE TABLE typing_result (
    isolate_id   TEXT NOT NULL REFERENCES isolate(isolate_id),
    run_id       TEXT NOT NULL REFERENCES pipeline_run(run_id),
    mlst_st      TEXT,
    clonal_complex TEXT,
    PRIMARY KEY (isolate_id, run_id)
);

CREATE TABLE cluster_assignment (
    isolate_id   TEXT NOT NULL REFERENCES isolate(isolate_id),
    run_id       TEXT NOT NULL REFERENCES pipeline_run(run_id),
    method       TEXT NOT NULL CHECK (method IN ('cgMLST', 'SNP')),
    threshold    INTEGER NOT NULL,       -- alleles (cgMLST) or SNPs
    cluster_name TEXT NOT NULL,          -- ReporTree name; stable across runs via --nomenclature-file
    PRIMARY KEY (isolate_id, run_id, method, threshold)
);

-- AMR rows follow hAMRonization (PHA4GE) field meanings so any AMR tool maps in.
CREATE TABLE amr_result (
    isolate_id            TEXT NOT NULL REFERENCES isolate(isolate_id),
    run_id                TEXT NOT NULL REFERENCES pipeline_run(run_id),
    gene_symbol           TEXT NOT NULL,
    drug_class            TEXT,
    analysis_software_name    TEXT NOT NULL,
    analysis_software_version TEXT NOT NULL,
    reference_database_version TEXT NOT NULL,
    coverage_percentage   REAL,
    sequence_identity     REAL
);

-- The release step a LIMS enforces: nothing is reported without QC pass and a reviewer.
CREATE TABLE report_release (
    isolate_id     TEXT NOT NULL REFERENCES isolate(isolate_id),
    run_id         TEXT NOT NULL REFERENCES pipeline_run(run_id),
    report_type    TEXT NOT NULL CHECK (report_type IN ('isolate_clinical', 'cluster_public_health')),
    report_version TEXT NOT NULL,
    reviewed_by    TEXT NOT NULL,
    released_at    TEXT NOT NULL,
    PRIMARY KEY (isolate_id, run_id, report_type, report_version)
);

-- Exercise queries for M6 (write these yourself; check each answer against the CSVs):
--   Q1 Which isolates failed QC in the latest run, and why?
--   Q2 At the frozen threshold, list each cluster with size, first and last collection date, states.
--   Q3 Which isolates changed cluster between two runs? (needs two pipeline_run rows)
--   Q4 Do cgMLST and SNP assignments disagree for any isolate at the paired thresholds?
--   Q5 Which isolates have a QC pass but no report_release row (the release backlog)?
