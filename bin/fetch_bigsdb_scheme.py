#!/usr/bin/env python3
"""Download every locus FASTA of a BIGSdb scheme (default: Pasteur cgMLST1748) (M2).

One FASTA per locus, which is the layout chewBBACA PrepExternalSchema expects.
Each file is checked (non-empty, every record header is "<locus>_<n>", sequence is
ACGT only) before it is kept; a failed check deletes the file so a rerun refetches it.
Existing verified files are skipped, so the script resumes.

Writes <outdir>/../<scheme_name>_download.tsv: locus, alleles, sha256 of the FASTA,
plus a header line with the scheme, its locus count from the API and the download date.
Exits 1 unless every locus listed by the API is present and verified.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

API = "https://bigsdb.pasteur.fr/api/db/{db}"
SEQ_OK = re.compile(r"^[ACGT]+$")


def log(msg):
    print(f"[fetch_bigsdb_scheme] {msg}", file=sys.stderr, flush=True)


def get(url, retries=8):
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=300) as resp:
                return resp.read()
        except (urllib.error.URLError, OSError) as e:
            if attempt == retries:
                raise RuntimeError(f"GET {url} failed after {retries} tries: {e}")
            time.sleep(min(60, 5 * 2 ** (attempt - 1)))


def check_fasta(locus, data):
    """Return the allele count, or raise if the FASTA is not what we expect."""
    text = data.decode()
    if not text.startswith(">"):
        raise ValueError(f"{locus}: not FASTA")
    n = 0
    for rec in text.split(">")[1:]:
        header, _, seq = rec.partition("\n")
        name = header.split()[0]
        if not re.fullmatch(re.escape(locus) + r"_\d+", name):
            raise ValueError(f"{locus}: unexpected header {name!r}")
        seq = seq.replace("\n", "").strip()
        if not SEQ_OK.match(seq):
            raise ValueError(f"{locus}: allele {name} has non-ACGT characters")
        n += 1
    return n


def fetch_locus(api, locus, outdir):
    path = os.path.join(outdir, f"{locus}.fasta")
    if os.path.exists(path):
        data = open(path, "rb").read()
        return locus, check_fasta(locus, data), hashlib.sha256(data).hexdigest(), "existing"
    data = get(f"{api}/loci/{locus}/alleles_fasta")
    n = check_fasta(locus, data)  # raises before anything is written
    with open(path + ".part", "wb") as fh:
        fh.write(data)
    os.replace(path + ".part", path)
    return locus, n, hashlib.sha256(data).hexdigest(), "downloaded"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", default="pubmlst_listeria_seqdef")
    p.add_argument("--scheme", type=int, default=3)
    p.add_argument("--outdir", default="data/schema/pasteur_cgmlst1748_raw")
    p.add_argument("--jobs", type=int, default=4)
    args = p.parse_args()

    api = API.format(db=args.db)
    meta = json.loads(get(f"{api}/schemes/{args.scheme}"))
    loci = [u.rstrip("/").split("/")[-1] for u in json.loads(get(f"{api}/schemes/{args.scheme}/loci"))["loci"]]
    name = meta.get("description", f"scheme{args.scheme}")
    log(f"{name}: API locus_count={meta.get('locus_count')}, loci listed={len(loci)}")
    os.makedirs(args.outdir, exist_ok=True)

    results, failed = {}, {}
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(fetch_locus, api, l, args.outdir): l for l in loci}
        for i, fut in enumerate(as_completed(futures), 1):
            locus = futures[fut]
            try:
                results[locus] = fut.result()
            except Exception as e:
                failed[locus] = str(e)
                bad = os.path.join(args.outdir, f"{locus}.fasta")
                if os.path.exists(bad):
                    os.remove(bad)
                log(f"{locus}: FAILED - {e}")
            if i % 200 == 0:
                log(f"{i}/{len(loci)} loci")

    manifest = os.path.join(os.path.dirname(args.outdir.rstrip("/")), f"{os.path.basename(args.outdir.rstrip('/'))}_download.tsv")
    with open(manifest, "w") as fh:
        fh.write(f"# {args.db} scheme {args.scheme} ({name}); API locus_count={meta.get('locus_count')}; "
                 f"loci listed={len(loci)}; {time.strftime('%Y-%m-%dT%H:%M:%S%z')}\n")
        fh.write("locus\talleles\tsha256\n")
        for l in loci:
            if l in results:
                fh.write(f"{l}\t{results[l][1]}\t{results[l][2]}\n")
    total = sum(r[1] for r in results.values())
    log(f"verified {len(results)}/{len(loci)} loci, {total} alleles -> {manifest}")
    if failed:
        log(f"{len(failed)} loci failed; rerun to retry")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
