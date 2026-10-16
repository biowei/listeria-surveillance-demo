#!/usr/bin/env python3
"""Build data/metadata.tsv from NCBI BioSample for every isolate in data/runs.tsv (M2).

Columns follow the `isolate` table in db/schema.sql (PHA4GE minimal contextual field
names in snake_case), plus isolation_source and source_type, which the reports need
to tell food from clinical isolates.

Values come from BioSample attributes only. NCBI null words ("missing",
"not collected", ...) become empty. Nothing is invented: purpose_of_sampling and
purpose_of_sequencing stay empty unless BioSample carries them, and no date is filled,
so date_is_synthetic is 0 on every row this script writes.

The raw attributes of every BioSample are saved to data/biosample_attributes.tsv
(long format, not committed), so each value can be traced back.
"""

import argparse
import csv
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
NULLS = {"", "missing", "not collected", "not applicable", "not provided", "na", "n/a",
         "none", "unknown", "not available", "not determined", "restricted access",
         "missing: control sample", "-"}
ISO_DATE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")
COLUMNS = ["isolate_id", "biosample_accession", "sra_run_accession", "organism",
           "sample_collection_date", "date_is_synthetic", "geo_loc_name_country",
           "geo_loc_name_state", "sample_collected_by", "sequenced_by",
           "purpose_of_sampling", "purpose_of_sequencing", "data_custodian_organization",
           "dataset_source", "truth_outbreak", "isolation_source", "source_type"]


def log(msg):
    print(f"[build_metadata] {msg}", file=sys.stderr, flush=True)


def clean(v):
    v = (v or "").strip()
    return "" if v.lower() in NULLS else v


def fetch_biosamples(accessions, batch=100):
    out = {}
    for i in range(0, len(accessions), batch):
        ids = ",".join(accessions[i:i + batch])
        url = f"{EFETCH}?{urllib.parse.urlencode({'db': 'biosample', 'id': ids, 'retmode': 'xml'})}"
        for attempt in range(1, 6):
            try:
                with urllib.request.urlopen(url, timeout=120) as resp:
                    root = ET.fromstring(resp.read())
                break
            except OSError as e:
                if attempt == 5:
                    raise
                log(f"efetch failed ({e}); retry {attempt}/4")
                time.sleep(5 * attempt)
        for bs in root.findall("BioSample"):
            attrs = {}
            for a in bs.findall("Attributes/Attribute"):
                key = a.get("harmonized_name") or a.get("attribute_name")
                attrs[key] = (a.text or "").strip()
            owner = bs.find("Owner/Name")
            org = bs.find("Description/Organism")
            out[bs.get("accession")] = {
                "attrs": attrs,
                "owner": (owner.text or "").strip() if owner is not None else "",
                # taxonomy_name can carry a strain ("Listeria monocytogenes CFSAN002349")
                "organism": " ".join(org.get("taxonomy_name", "").split()[:2]) if org is not None else "",
            }
        time.sleep(0.4)  # stay under the E-utilities limit of 3 requests/s without a key
    return out


def split_geo(geo):
    """'USA: California, Fresno' -> ('USA', 'California')."""
    if not geo:
        return "", ""
    country, _, rest = geo.partition(":")
    state = rest.split(",")[0].strip()
    return country.strip(), state


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--runs", default="data/runs.tsv")
    p.add_argument("--out", default="data/metadata.tsv")
    p.add_argument("--raw", default="data/biosample_attributes.tsv")
    args = p.parse_args()

    with open(args.runs) as fh:
        runs = list(csv.DictReader(fh, delimiter="\t"))
    accs = [r["biosample_acc"] for r in runs]
    got = fetch_biosamples(accs)
    missing = [a for a in accs if a not in got]
    if missing:
        sys.exit(f"BioSample records not returned: {', '.join(missing)}")

    rows, raw, nonstandard_dates = [], [], []
    for r in runs:
        bs = got[r["biosample_acc"]]
        a = bs["attrs"]
        for k in sorted(a):
            raw.append({"biosample_accession": r["biosample_acc"], "attribute": k, "value": a[k]})
        date = clean(a.get("collection_date"))
        if date and not ISO_DATE.match(date):
            nonstandard_dates.append((r["biosample_acc"], date))
        country, state = split_geo(clean(a.get("geo_loc_name")))
        rows.append({
            "isolate_id": r["sample_id"],
            "biosample_accession": r["biosample_acc"],
            "sra_run_accession": r["run_accession"],
            "organism": bs["organism"],
            "sample_collection_date": date,
            "date_is_synthetic": "0",
            "geo_loc_name_country": country,
            "geo_loc_name_state": state,
            "sample_collected_by": clean(a.get("collected_by")),
            "sequenced_by": clean(a.get("sequenced_by")),
            "purpose_of_sampling": clean(a.get("purpose_of_sampling")),
            "purpose_of_sequencing": clean(a.get("purpose_of_sequencing")),
            "data_custodian_organization": bs["owner"],
            "dataset_source": r["dataset_source"],
            "truth_outbreak": r["truth_outbreak"],
            "isolation_source": clean(a.get("isolation_source")),
            "source_type": clean(a.get("source_type")),
        })

    for path, cols, data in ((args.out, COLUMNS, rows),
                             (args.raw, ["biosample_accession", "attribute", "value"], raw)):
        with open(path + ".tmp", "w", newline="") as fh:
            w = csv.DictWriter(fh, cols, delimiter="\t", lineterminator="\n")
            w.writeheader()
            w.writerows(data)
        os.replace(path + ".tmp", path)

    n = len(rows)
    dated = [x["sample_collection_date"] for x in rows if x["sample_collection_date"]]
    full = [d for d in dated if re.match(r"^\d{4}-\d{2}-\d{2}$", d)]
    log(f"wrote {args.out}: {n} isolates")
    log(f"collection date present: {len(dated)}/{n} (full day: {len(full)}, "
        f"month or year only: {len(dated) - len(full)})")
    for col in ("geo_loc_name_country", "geo_loc_name_state", "sample_collected_by",
                "sequenced_by", "purpose_of_sampling", "purpose_of_sequencing",
                "isolation_source", "source_type"):
        log(f"{col} present: {sum(bool(x[col]) for x in rows)}/{n}")
    for acc, d in nonstandard_dates:
        log(f"non-ISO collection_date kept as given: {acc} {d!r}")


if __name__ == "__main__":
    main()
