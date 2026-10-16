#!/usr/bin/env python3
"""Apply the frozen SPEC-A selection rule (validation/acceptance_criteria.md, steps 3-6).

Step 3, metadata filter (snapshot files only):
  not in the Timme sheet; SNP cluster present and not an outbreak cluster;
  collection_date year (first 4 chars) within --years; non-empty asm_acc and an SRA run.
Step 4, cluster CC (assumption: a PD SNP cluster does not span CCs):
  per SNP cluster, type survivors in ascending BioSample order until one result counts
  (exact ST with a CC), at most 3 tries; that is the cluster's CC. Runs --jobs clusters
  in parallel; each cluster's result depends only on its own isolates.
Step 5, selection walk over survivors in --cc clusters, sorted by BioSample accession:
  a. skip if the SNP cluster already has a selected isolate
  b. first SRA run must be ILLUMINA + PAIRED in the ENA catalogue
  c. type the isolate itself; must count and be --cc (else recorded against the assumption)
  d. select; stop at --n.
Step 6: if the list runs out before --n, report the shortfall (exit 2), widen nothing.

Network failures stop the script rather than skipping an isolate, because a skip
caused by a transient error would change the selection. ENA, typing and BIGSdb
results are cached in --workdir, so a rerun resumes where it stopped.

Outputs:
  --clusters-log  every SNP cluster: isolates tried in step 4 and the cluster CC
  --log       every isolate the step 5 walk reached, with the step that decided it
  --selected  the selected isolates
  --runs      with --append-runs, SPEC-A rows appended (only when all N were selected)
"""

import argparse
import csv
import io
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed

ENA_FILEREPORT = "https://www.ebi.ac.uk/ena/portal/api/filereport"
NCBI_GENOME = "https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession/{}/download?include_annotation_type=GENOME_FASTA"
BIGSDB_PROFILE = "https://bigsdb.pasteur.fr/api/db/pubmlst_listeria_seqdef/schemes/2/profiles/{}"
MLST_IMAGE = "staphb/mlst@sha256:d11a9ea089158c8648852f44ea7de495ea60001acb9850127b73b904e7c73642"
LOCK = threading.Lock()
RUN_RE = re.compile(r"^[SED]RR\d+$")
CLUSTER_COLUMNS = ["pds", "n_survivors", "tried", "cluster_cc", "status"]
LOG_COLUMNS = ["order", "biosample_acc", "pds", "run", "asm_acc", "collection_date",
               "decision", "detail", "st", "cc"]


def log(msg):
    print(f"[select_spec_a] {msg}", file=sys.stderr, flush=True)


def empty(v):
    return v is None or v.strip() in ("", "NULL", "missing", "-")


def strip_version(pds):
    return pds.split(".")[0]


def http_get(url, binary=False, retries=8):
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=120) as resp:
                data = resp.read()
                return data if binary else data.decode()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise RuntimeError(f"GET {url}: 404")
            if attempt == retries:
                raise RuntimeError(f"GET {url} failed after {retries} tries: {e}")
            time.sleep(min(60, 5 * 2 ** (attempt - 1)))
        except OSError as e:
            if attempt == retries:
                raise RuntimeError(f"GET {url} failed after {retries} tries: {e}")
            time.sleep(min(60, 5 * 2 ** (attempt - 1)))


class Cache:
    """Small JSON cache so a rerun does not repeat network calls or typing."""

    def __init__(self, path):
        self.path = path
        self.data = json.load(open(path)) if os.path.exists(path) else {}

    def get(self, key):
        return self.data.get(key)

    def put(self, key, value):
        with LOCK:
            self.data[key] = value
            tmp = self.path + ".tmp"
            with open(tmp, "w") as fh:
                json.dump(self.data, fh, indent=0, sort_keys=True)
            os.replace(tmp, self.path)


# ---------------------------------------------------------------- step 3

def timme_biosamples(sheet):
    with open(sheet) as fh:
        lines = fh.read().splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("biosample_acc\t"))
    return {r["biosample_acc"] for r in csv.DictReader(lines[start:], delimiter="\t")}


def metadata_filter(args):
    lo, hi = (int(y) for y in args.years.split("-"))
    exclude_pds = {strip_version(p) for p in args.exclude_pds.split(",")}
    timme = timme_biosamples(args.timme_sheet)

    pds_of = {}  # biosample -> set of PDS (unversioned)
    with open(args.clusters) as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            if not empty(r["PDS_acc"]):
                pds_of.setdefault(r["biosample_acc"], set()).add(strip_version(r["PDS_acc"]))

    # metadata has one row per PD target; group by BioSample, targets in accession order
    rows = {}
    with open(args.metadata) as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            rows.setdefault(r["biosample_acc"], []).append(r)

    counts = {"biosamples_in_snapshot": len(rows)}
    survivors, conflicts = [], []
    stage = {"not_timme": 0, "clustered": 0, "not_outbreak_cluster": 0, "year": 0, "asm_and_run": 0}
    for bs in sorted(rows):
        if bs in timme:
            continue
        stage["not_timme"] += 1
        clusters = pds_of.get(bs, set())
        if not clusters:
            continue
        stage["clustered"] += 1
        if len(clusters) > 1:
            conflicts.append((bs, sorted(clusters)))  # reported; no rule covers it
            continue
        pds = next(iter(clusters))
        if pds in exclude_pds:
            continue
        stage["not_outbreak_cluster"] += 1
        targets = sorted(rows[bs], key=lambda r: r["target_acc"])
        years = {t["collection_date"][:4] for t in targets if not empty(t["collection_date"])}
        years = {int(y) for y in years if y.isdigit()}
        if len(years) != 1 or not lo <= next(iter(years)) <= hi:
            continue
        stage["year"] += 1
        pick = None
        for t in targets:
            runs = [x.strip() for x in t["Run"].split(",") if RUN_RE.match(x.strip())]
            if not empty(t["asm_acc"]) and runs:
                pick = (t, runs[0])
                break
        if pick is None:
            continue
        stage["asm_and_run"] += 1
        t, run = pick
        survivors.append({"biosample_acc": bs, "pds": pds, "run": run, "asm_acc": t["asm_acc"],
                          "collection_date": t["collection_date"], "strain": t["strain"]})
    counts.update(stage)
    counts["pds_conflicts_excluded"] = len(conflicts)
    return survivors, counts, conflicts


# ---------------------------------------------------------------- step 4

def ena_check(run, cache):
    hit = cache.get(f"ena:{run}")
    if hit is None:
        q = urllib.parse.urlencode({"accession": run, "result": "read_run",
                                    "fields": "run_accession,instrument_platform,library_layout",
                                    "format": "tsv"})
        for attempt in range(1, 4):
            recs = list(csv.DictReader(http_get(f"{ENA_FILEREPORT}?{q}").splitlines(), delimiter="\t"))
            if recs:
                break
            time.sleep(5 * attempt)  # ENA sometimes returns an empty report transiently
        if not recs:
            hit = {"platform": "NOT_IN_ENA", "layout": ""}
        else:
            hit = {"platform": recs[0]["instrument_platform"], "layout": recs[0]["library_layout"]}
        cache.put(f"ena:{run}", hit)
    return hit


def fetch_assembly(asm, asm_dir):
    out = os.path.join(asm_dir, f"{asm}.fna")
    if os.path.exists(out):
        return out
    data = http_get(NCBI_GENOME.format(asm), binary=True)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        fna = [n for n in z.namelist() if n.endswith(".fna")]
        if len(fna) != 1:
            raise RuntimeError(f"{asm}: expected one .fna in NCBI package, got {len(fna)}")
        with open(out + ".part", "wb") as fh:
            fh.write(z.read(fna[0]))
    os.replace(out + ".part", out)
    return out


class Mlst:
    """One long-lived container; `docker exec` per assembly."""

    def __init__(self, asm_dir):
        self.asm_dir = os.path.abspath(asm_dir)
        self.name = f"select_spec_a_{os.getpid()}"
        subprocess.run(["docker", "run", "-d", "--rm", "--platform", "linux/amd64",
                        "--name", self.name, "-v", f"{self.asm_dir}:/data", "-w", "/data",
                        MLST_IMAGE, "sleep", "infinity"], check=True, capture_output=True)

    def type(self, fna):
        res = subprocess.run(["docker", "exec", self.name, "mlst", "--quiet", "--scheme",
                              "listeria_2", os.path.basename(fna)],
                             check=True, capture_output=True, text=True)
        cols = res.stdout.strip().split("\t")
        return cols[2], "\t".join(cols[3:])  # ST, alleles

    def close(self):
        subprocess.run(["docker", "rm", "-f", self.name], capture_output=True)


def st_to_cc(st, cache):
    hit = cache.get(f"cc:{st}")
    if hit is None:
        try:
            prof = json.loads(http_get(BIGSDB_PROFILE.format(st)))
        except RuntimeError as e:
            if "404" in str(e):
                prof = {}
            else:
                raise
        hit = prof.get("CC") or ""
        cache.put(f"cc:{st}", hit)
    return hit


def type_isolate(iso, mlst, asm_dir, cache):
    """Typing as defined in the rule. Returns (st, cc, counts, detail)."""
    typed = cache.get(f"mlst:{iso['asm_acc']}")
    if typed is None:
        try:
            fna = fetch_assembly(iso["asm_acc"], asm_dir)
        except RuntimeError as e:
            if not str(e).endswith(": 404"):
                raise  # network trouble: stop, never count it as a try
            typed = {"st": "", "alleles": "assembly not available (404)"}
        else:
            st, alleles = mlst.type(fna)
            typed = {"st": st, "alleles": alleles}
        cache.put(f"mlst:{iso['asm_acc']}", typed)
    st = typed["st"]
    if not st.isdigit():
        return st, "", False, typed["alleles"]
    cc = st_to_cc(st, cache)
    return st, cc, bool(cc), "" if cc else "ST without CC"


def cluster_ccs(survivors, args, cache, mlst, asm_dir):
    by_cluster = {}
    for iso in survivors:  # survivors are already in BioSample order
        by_cluster.setdefault(iso["pds"], []).append(iso)

    def one(pds):
        tried = []
        for iso in by_cluster[pds][:3]:
            st, cc, counts, detail = type_isolate(iso, mlst, asm_dir, cache)
            tried.append(f"{iso['biosample_acc']}:{st or '-'}:{cc or '-'}")
            if counts:
                return {"pds": pds, "n_survivors": len(by_cluster[pds]), "tried": ";".join(tried),
                        "cluster_cc": cc, "status": "typed"}
        return {"pds": pds, "n_survivors": len(by_cluster[pds]), "tried": ";".join(tried),
                "cluster_cc": "", "status": "excluded_no_counting_result_in_3"}

    results, done = {}, 0
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(one, pds): pds for pds in by_cluster}
        for fut in as_completed(futures):
            r = fut.result()  # an exception here stops the run; the cache keeps progress
            results[r["pds"]] = r
            done += 1
            if done % 100 == 0:
                n_cc = sum(x["cluster_cc"] == args.cc for x in results.values())
                log(f"step 4: {done}/{len(by_cluster)} clusters typed, {n_cc} {args.cc}")
    return [results[k] for k in sorted(results)]


def selection_walk(survivors, cc_clusters, args, cache, mlst, asm_dir):
    taken, selected, walked = set(), [], []
    pool = [s for s in survivors if s["pds"] in cc_clusters]
    for i, iso in enumerate(pool, 1):
        rec = dict(iso, order=i, st="", cc="", detail="")
        if iso["pds"] in taken:
            rec["decision"] = "skip_5a_cluster_taken"
            walked.append(rec)
            continue
        ena = ena_check(iso["run"], cache)
        if ena["platform"] != "ILLUMINA" or ena["layout"] != "PAIRED":
            rec["decision"] = "skip_5b_not_illumina_paired"
            rec["detail"] = f"{ena['platform']}/{ena['layout']}"
            walked.append(rec)
            continue
        st, cc, counts, detail = type_isolate(iso, mlst, asm_dir, cache)
        rec.update(st=st, cc=cc, detail=detail)
        if not counts or cc != args.cc:
            rec["decision"] = "skip_5c_not_confirmed_against_assumption"
            walked.append(rec)
            log(f"step 5c: {iso['biosample_acc']} in {args.cc} cluster {iso['pds']} typed "
                f"ST{st or '-'} {cc or '-'} (evidence against the step 4 assumption)")
            continue
        rec["decision"] = "selected"
        taken.add(iso["pds"])
        selected.append(rec)
        walked.append(rec)
        log(f"selected {len(selected)}/{args.n}: {iso['biosample_acc']} {iso['pds']} ST{st}")
        if len(selected) == args.n:
            break
    return selected, walked


# ---------------------------------------------------------------- outputs

def write_tsv(path, columns, rows):
    tmp = path + ".tmp"
    with open(tmp, "w", newline="") as fh:
        w = csv.DictWriter(fh, columns, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)


def append_runs(path, selected, snapshot):
    with open(path) as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        cols, existing = reader.fieldnames, list(reader)
    if any(r["arm"] == "SPEC-A" for r in existing):
        sys.exit(f"{path} already has SPEC-A rows; refusing to append twice")
    for s in selected:
        existing.append({"sample_id": s["biosample_acc"], "run_accession": s["run"],
                         "biosample_acc": s["biosample_acc"], "arm": "SPEC-A",
                         "truth_outbreak": "0", "dataset_source": f"NCBI_PD_{snapshot}",
                         "timme_sha256_r1": "", "timme_sha256_r2": ""})
    write_tsv(path, cols, existing)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--metadata", required=True)
    p.add_argument("--clusters", required=True)
    p.add_argument("--timme-sheet", default="data/Listeria_monocytogenes_1408MLGX6-3WGS.tsv")
    p.add_argument("--exclude-pds", default="PDS000024934,PDS000024956")
    p.add_argument("--years", default="2010-2016")
    p.add_argument("--cc", default="CC183")
    p.add_argument("--n", type=int, default=40)
    p.add_argument("--workdir", default="data/spec_a_work")
    p.add_argument("--jobs", type=int, default=8, help="clusters typed in parallel in step 4")
    p.add_argument("--clusters-log", default="data/spec_a_clusters.tsv")
    p.add_argument("--log", default="data/spec_a_selection.tsv")
    p.add_argument("--selected", default="data/spec_a_selected.tsv")
    p.add_argument("--runs", default="data/runs.tsv")
    p.add_argument("--append-runs", action="store_true")
    args = p.parse_args()

    snapshot = os.path.basename(args.metadata).split(".metadata")[0]
    if not os.path.basename(args.clusters).startswith(snapshot):
        sys.exit(f"metadata ({snapshot}) and cluster list are from different snapshots")
    os.makedirs(args.workdir, exist_ok=True)
    cache = Cache(os.path.join(args.workdir, "cache.json"))

    survivors, counts, conflicts = metadata_filter(args)
    for k, v in counts.items():
        log(f"step 3 {k}: {v}")
    for bs, cl in conflicts:
        log(f"step 3 excluded, BioSample in more than one SNP cluster: {bs} {cl}")
    log(f"step 3 survivors: {len(survivors)} in {len({s['pds'] for s in survivors})} SNP clusters")

    asm_dir = os.path.join(args.workdir, "assemblies")
    os.makedirs(asm_dir, exist_ok=True)
    mlst = Mlst(asm_dir)
    try:
        clusters = cluster_ccs(survivors, args, cache, mlst, asm_dir)
        write_tsv(args.clusters_log, CLUSTER_COLUMNS, clusters)
        cc_clusters = {c["pds"] for c in clusters if c["cluster_cc"] == args.cc}
        excluded = [c["pds"] for c in clusters if c["status"] != "typed"]
        log(f"step 4: {len(clusters)} clusters; {len(cc_clusters)} {args.cc}; "
            f"{len(excluded)} excluded (no counting result in 3 tries)")
        selected, walked = selection_walk(survivors, cc_clusters, args, cache, mlst, asm_dir)
    finally:
        mlst.close()
    write_tsv(args.log, LOG_COLUMNS, walked)
    write_tsv(args.selected, LOG_COLUMNS, selected)
    tally = {}
    for w in walked:
        tally[w["decision"]] = tally.get(w["decision"], 0) + 1
    for k in sorted(tally):
        log(f"step 5 {k}: {tally[k]}")
    with open(os.path.join(args.workdir, "summary.json"), "w") as fh:
        json.dump({"snapshot": snapshot, "step3": counts, "step3_survivors": len(survivors),
                   "step4_clusters": len(clusters), "step4_cc_clusters": len(cc_clusters),
                   "step4_excluded": excluded, "step5": tally, "selected": len(selected), "n": args.n}, fh, indent=1)

    if len(selected) < args.n:
        log(f"SHORTFALL: {len(selected)}/{args.n} selected; list exhausted (rule step 6). "
            "runs.tsv not changed.")
        return 2
    if args.append_runs:
        append_runs(args.runs, selected, snapshot)
        log(f"appended {len(selected)} SPEC-A rows to {args.runs}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
