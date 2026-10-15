#!/usr/bin/env python3
"""Stage paired Illumina reads from ENA and verify them (milestone M2).

Procedure (docs/data_staging.md section 3), per run accession:
  1. look up the ENA catalogue (read_count, fastq_ftp, fastq_md5) -- never from memory;
  2. download both mates over HTTPS to a .part file, then rename;
  3. md5 of each file equals ENA fastq_md5;
  4. read count of R1 and of R2 equals ENA read_count (lines > 0, lines % 4 == 0);
  5. read names in R1 and R2 match (after stripping /1 /2 and comments);
     on any failure in 3-5 BOTH mates are deleted so a rerun refetches them;
  6. a verified run gets a sidecar <run>.verified.json;
  7. the manifest and the bacass samplesheet are rebuilt from the files on disk
     (md5 recomputed and compared with the sidecar); exit 1 if any run is missing.

Subcommands:
  timme     Timme benchmark sheet -> runs.tsv (SENS + SPEC-T rows)
  fetch     runs.tsv -> verified FASTQ, then rebuild manifest + samplesheet
  manifest  rebuild manifest + samplesheet only (no network)

Standard library only. Public data only (see CLAUDE.md data rules).
"""

import argparse
import csv
import gzip
import hashlib
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

ENA_FILEREPORT = "https://www.ebi.ac.uk/ena/portal/api/filereport"
ENA_FIELDS = "run_accession,read_count,fastq_ftp,fastq_md5,library_layout,instrument_platform"
RUNS_COLUMNS = ["sample_id", "run_accession", "biosample_acc", "arm", "truth_outbreak",
                "dataset_source", "timme_sha256_r1", "timme_sha256_r2"]
MANIFEST_COLUMNS = ["sample_id", "run_accession", "arm", "status", "read_count",
                    "r1", "r1_md5", "r2", "r2_md5", "pairing_ok", "timme_sha256_match",
                    "verified_at"]
CHUNK = 1 << 20


def log(msg):
    print(f"[stage_reads] {msg}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------- runs.tsv

def cmd_timme(args):
    """Convert the Timme sheet (metadata header block, then a table) to runs.tsv."""
    with open(args.sheet) as fh:
        lines = fh.read().splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("biosample_acc\t"))
    rows = list(csv.DictReader(lines[start:], delimiter="\t"))
    out = []
    for r in rows:
        is_outbreak = r["outbreak"] != "outgroup"
        out.append({
            "sample_id": r["strain"],
            "run_accession": r["SRArun_acc"],
            "biosample_acc": r["biosample_acc"],
            "arm": "SENS" if is_outbreak else "SPEC-T",
            "truth_outbreak": "1" if is_outbreak else "0",
            "dataset_source": "Timme2017_1408MLGX6-3WGS",
            "timme_sha256_r1": r["sha256sumRead1"],
            "timme_sha256_r2": r["sha256sumRead2"],
        })
    write_tsv(args.out, RUNS_COLUMNS, out)
    n_sens = sum(r["arm"] == "SENS" for r in out)
    log(f"wrote {args.out}: {len(out)} runs ({n_sens} SENS, {len(out) - n_sens} SPEC-T)")
    ref = [r["strain"] for r in rows if r["suggestedReference"].upper() == "TRUE"]
    log(f"suggestedReference: {', '.join(ref) or 'none'}")


def read_runs(path):
    with open(path) as fh:
        runs = list(csv.DictReader(fh, delimiter="\t"))
    seen = set()
    for r in runs:
        for col in ("sample_id", "run_accession"):
            if not r.get(col):
                sys.exit(f"{path}: row without {col}: {r}")
        if r["sample_id"] in seen:
            sys.exit(f"{path}: duplicate sample_id {r['sample_id']}")
        seen.add(r["sample_id"])
    return runs


def write_tsv(path, columns, rows):
    tmp = path + ".tmp"
    with open(tmp, "w", newline="") as fh:
        w = csv.DictWriter(fh, columns, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)


# ---------------------------------------------------------------- ENA catalogue

def http_get(url, retries=4):
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                return resp.read().decode()
        except OSError as e:
            if attempt == retries:
                raise
            log(f"GET failed ({e}); retry {attempt}/{retries - 1}")
            time.sleep(5 * attempt)


def ena_record(run):
    q = urllib.parse.urlencode({"accession": run, "result": "read_run",
                                "fields": ENA_FIELDS, "format": "tsv"})
    rows = list(csv.DictReader(http_get(f"{ENA_FILEREPORT}?{q}").splitlines(), delimiter="\t"))
    if len(rows) != 1:
        raise RuntimeError(f"{run}: expected 1 ENA record, got {len(rows)}")
    return rows[0]


def paired_files(rec):
    """Return [(url, md5), (url, md5)] for _1 and _2; ignore an unpaired third file."""
    urls = [u for u in rec["fastq_ftp"].split(";") if u]
    md5s = [m for m in rec["fastq_md5"].split(";") if m]
    if len(urls) != len(md5s):
        raise RuntimeError(f"{rec['run_accession']}: fastq_ftp/fastq_md5 length mismatch")
    pairs = dict(zip(urls, md5s))
    mates = []
    for suffix in ("_1.fastq.gz", "_2.fastq.gz"):
        hit = [u for u in pairs if u.endswith(suffix)]
        if len(hit) != 1:
            raise RuntimeError(f"{rec['run_accession']}: no single *{suffix} in ENA record "
                               f"(layout={rec.get('library_layout')})")
        mates.append(("https://" + hit[0], pairs[hit[0]]))
    return mates


# ---------------------------------------------------------------- verification

def file_hash(path, algo):
    h = hashlib.new(algo)
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def read_name(header):
    name = header.split()[0]
    if name.endswith((b"/1", b"/2")):
        name = name[:-2]
    return name


def count_and_pair(r1, r2):
    """One pass over both mates: read counts, FASTQ shape, and read-name pairing.

    Returns (n1, n2, pairing_ok, first_mismatch)."""
    n = 0
    mismatch = None
    with gzip.open(r1, "rb") as f1, gzip.open(r2, "rb") as f2:
        while True:
            h1, h2 = f1.readline(), f2.readline()
            if not h1 or not h2:
                break
            for _ in range(3):
                if not f1.readline() or not f2.readline():
                    raise RuntimeError(f"{os.path.basename(r1)}: truncated record after read {n} (lines % 4 != 0)")
            if not h1.startswith(b"@") or not h2.startswith(b"@"):
                raise RuntimeError(f"{os.path.basename(r1)}: record {n + 1} header does not start with '@'")
            if mismatch is None and read_name(h1) != read_name(h2):
                mismatch = (n + 1, read_name(h1).decode(), read_name(h2).decode())
            n += 1
        extra1, extra2 = h1 or f1.readline(), h2 or f2.readline()
    n1 = n + (1 if extra1 else 0)
    n2 = n + (1 if extra2 else 0)
    return n1, n2, (mismatch is None and n1 == n2), mismatch


def download(url, dest):
    part = dest + ".part"
    for attempt in range(1, 5):
        try:
            with urllib.request.urlopen(url, timeout=120) as resp, open(part, "wb") as out:
                for block in iter(lambda: resp.read(CHUNK), b""):
                    out.write(block)
            os.replace(part, dest)
            return
        except OSError as e:
            if os.path.exists(part):
                os.remove(part)
            if attempt == 4:
                raise
            log(f"download {os.path.basename(dest)} failed ({e}); retry {attempt}/3")
            time.sleep(10 * attempt)


def remove_both(paths):
    for p in paths:
        if os.path.exists(p):
            os.remove(p)


def sidecar_path(fastq_dir, run):
    return os.path.join(fastq_dir, f"{run}.verified.json")


def stage_one(run_row, fastq_dir, catalogue):
    run = run_row["run_accession"]
    side = sidecar_path(fastq_dir, run)
    if os.path.exists(side):
        return run, "already verified"
    rec = ena_record(run)
    catalogue[run] = rec
    if rec.get("instrument_platform") != "ILLUMINA":
        raise RuntimeError(f"{run}: instrument_platform={rec.get('instrument_platform')}, not ILLUMINA")
    (u1, md5_1), (u2, md5_2) = paired_files(rec)
    expected = int(rec["read_count"])
    paths = [os.path.join(fastq_dir, f"{run}_1.fastq.gz"),
             os.path.join(fastq_dir, f"{run}_2.fastq.gz")]
    try:
        for url, path in ((u1, paths[0]), (u2, paths[1])):
            if not os.path.exists(path):
                download(url, path)
        got = [file_hash(p, "md5") for p in paths]
        for p, g, e in zip(paths, got, (md5_1, md5_2)):
            if g != e:
                raise RuntimeError(f"{os.path.basename(p)}: md5 {g} != ENA {e}")
        if expected <= 0:
            raise RuntimeError(f"{run}: ENA read_count={expected}")
        n1, n2, pairing_ok, mismatch = count_and_pair(*paths)
        if n1 != expected or n2 != expected:
            raise RuntimeError(f"{run}: read counts R1={n1} R2={n2}, ENA read_count={expected}")
        if not pairing_ok:
            raise RuntimeError(f"{run}: R1/R2 read names differ at read {mismatch[0]}: "
                               f"{mismatch[1]} vs {mismatch[2]}")
    except Exception:
        remove_both(paths)  # never leave a half-verified pair behind
        raise
    sha = [file_hash(p, "sha256") for p in paths]
    t1, t2 = run_row.get("timme_sha256_r1", ""), run_row.get("timme_sha256_r2", "")
    if t1 and t2 and t1 != "-":
        timme = "yes" if sha == [t1, t2] else "no"
    else:
        timme = "NA"
    with open(side, "w") as fh:
        json.dump({"run_accession": run, "read_count": expected,
                   "r1": os.path.basename(paths[0]), "r1_md5": got[0], "r1_sha256": sha[0],
                   "r2": os.path.basename(paths[1]), "r2_md5": got[1], "r2_sha256": sha[1],
                   "pairing_ok": True, "timme_sha256_match": timme,
                   "ena_fastq_ftp": rec["fastq_ftp"],
                   "verified_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, fh, indent=1)
    return run, f"verified ({expected} read pairs)"


def cmd_fetch(args):
    runs = read_runs(args.runs)
    os.makedirs(args.fastq_dir, exist_ok=True)
    catalogue, failures = {}, {}
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(stage_one, r, args.fastq_dir, catalogue): r["run_accession"]
                   for r in runs}
        for fut in as_completed(futures):
            run = futures[fut]
            try:
                log(f"{run}: {fut.result()[1]}")
            except Exception as e:
                failures[run] = str(e)
                log(f"{run}: FAILED - {e}")
    if catalogue:
        cat_path = os.path.join(os.path.dirname(args.manifest) or ".", "ena_catalogue.tsv")
        old = {}
        if os.path.exists(cat_path):
            with open(cat_path) as fh:
                old = {r["run_accession"]: r for r in csv.DictReader(fh, delimiter="\t")}
        old.update(catalogue)
        write_tsv(cat_path, ENA_FIELDS.split(","), [old[k] for k in sorted(old)])
    ok = build_manifest(args)
    if failures:
        log(f"{len(failures)} run(s) failed; rerun to retry")
    return 0 if ok and not failures else 1


# ---------------------------------------------------------------- manifest

def build_manifest(args):
    """Rebuild manifest + samplesheet from files on disk, never from the fetch log."""
    runs = read_runs(args.runs)
    rows, sheet, missing = [], [], []
    for r in runs:
        run = r["run_accession"]
        side = sidecar_path(args.fastq_dir, run)
        row = {"sample_id": r["sample_id"], "run_accession": run, "arm": r.get("arm", "")}
        meta = None
        if os.path.exists(side):
            with open(side) as fh:
                meta = json.load(fh)
            paths = [os.path.join(args.fastq_dir, meta[k]) for k in ("r1", "r2")]
            if not all(os.path.exists(p) for p in paths):
                meta, status = None, "missing_fastq"
            elif not args.fast and [file_hash(p, "md5") for p in paths] != [meta["r1_md5"], meta["r2_md5"]]:
                meta, status = None, "md5_changed_on_disk"
            else:
                status = "verified"
        else:
            status = "not_staged"
        if meta is None:
            missing.append(run)
            row["status"] = status
        else:
            row.update({k: meta[k] for k in ("read_count", "r1", "r1_md5", "r2", "r2_md5",
                                             "pairing_ok", "timme_sha256_match", "verified_at")})
            row["status"] = status
            sheet.append({"ID": r["sample_id"],
                          "R1": os.path.abspath(os.path.join(args.fastq_dir, meta["r1"])),
                          "R2": os.path.abspath(os.path.join(args.fastq_dir, meta["r2"])),
                          "LongFastQ": "NA", "Fast5": "NA", "GenomeSize": "NA"})
        rows.append(row)
    write_tsv(args.manifest, MANIFEST_COLUMNS, rows)
    write_tsv(args.samplesheet, ["ID", "R1", "R2", "LongFastQ", "Fast5", "GenomeSize"], sheet)
    log(f"manifest: {len(rows) - len(missing)}/{len(rows)} verified -> {args.manifest}")
    if missing:
        log(f"not verified: {', '.join(missing)}")
    return not missing


def cmd_manifest(args):
    return 0 if build_manifest(args) else 1


# ---------------------------------------------------------------- CLI

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("timme", help="Timme sheet -> runs.tsv")
    t.add_argument("--sheet", default="data/Listeria_monocytogenes_1408MLGX6-3WGS.tsv")
    t.add_argument("--out", default="data/runs.tsv")
    t.set_defaults(func=cmd_timme)

    for name, func, helptext in (("fetch", cmd_fetch, "download + verify, then rebuild manifest"),
                                 ("manifest", cmd_manifest, "rebuild manifest only")):
        s = sub.add_parser(name, help=helptext)
        s.add_argument("--runs", default="data/runs.tsv")
        s.add_argument("--fastq-dir", default="data/fastq")
        s.add_argument("--manifest", default="data/staging_manifest.tsv")
        s.add_argument("--samplesheet", default="data/samplesheet.tsv")
        s.add_argument("--fast", action="store_true",
                       help="manifest: trust sidecars, skip re-hashing files on disk")
        if name == "fetch":
            s.add_argument("--jobs", type=int, default=4, help="parallel runs (default 4)")
        s.set_defaults(func=func)

    args = p.parse_args()
    sys.exit(args.func(args) or 0)


if __name__ == "__main__":
    main()
