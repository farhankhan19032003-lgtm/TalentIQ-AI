"""Downloads the all-MiniLM-L6-v2 sentence-embedding model (about 90 MB) into backend/storage/models/all-MiniLM-L6-v2.

The app runs the model itself (sentence-transformers when installed, otherwise a pure NumPy implementation), so
nothing else is needed and no API is called at run time. Run once, with internet access:

    python scripts/fetch_minilm.py

Every file is checked against the hash and size that Hugging Face publishes for it, and discarded if it does not match."""
import hashlib
import sys
import urllib.request
from pathlib import Path

REPO = "sentence-transformers/all-MiniLM-L6-v2"
FILES = ["config.json", "vocab.txt", "tokenizer_config.json", "model.safetensors"]
DEST = Path(__file__).resolve().parents[1] / "backend" / "storage" / "models" / "all-MiniLM-L6-v2"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def published_facts(url: str) -> tuple[int, str]:
    """(size, sha256) as published by Hugging Face. The hash sits in the first response (a redirect to the CDN), which urllib
    would otherwise follow and lose, so redirects are switched off for this one request."""
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        r = opener.open(urllib.request.Request(url, method="HEAD"), timeout=60)
    except urllib.error.HTTPError as e:                                       # the 302 we expect
        r = e
    h = r.headers
    size = int(h.get("X-Linked-Size") or 0)              # only large (LFS) files publish their size and hash this way
    return size, (h.get("X-Linked-ETag") or "").strip('"')


def matches(path: Path, expected: str) -> bool:
    """True if the file has the hash Hugging Face publishes: SHA-256 for large (LFS) files, the 40-character git blob id for small ones."""
    if len(expected) == 64:
        return sha256(path) == expected
    if len(expected) == 40:
        data = path.read_bytes()
        return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest() == expected
    return True                                                                   # nothing published to compare with


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        url = f"https://huggingface.co/{REPO}/resolve/main/{name}"
        target = DEST / name
        size, expected = published_facts(url)                                  # expected = SHA-256 of LFS files (the weights)
        if target.exists() and (not size or target.stat().st_size == size) and matches(target, expected):
            print(f"ok      {name} ({target.stat().st_size:,} bytes, already present" + (", hash verified)" if expected else ")"))
            continue
        print(f"fetch   {name}" + (f" ({size:,} bytes)" if size else "") + " ...", flush=True)
        tmp = target.with_suffix(target.suffix + ".part")
        with urllib.request.urlopen(url, timeout=300) as r, open(tmp, "wb") as out:
            while chunk := r.read(1 << 20):
                out.write(chunk)
        if size and tmp.stat().st_size != size:
            tmp.unlink()
            print(f"FAILED  {name}: size {tmp.stat().st_size if tmp.exists() else '?'} != {size}")
            return 1
        if not matches(tmp, expected):
            tmp.unlink()
            print(f"FAILED  {name}: hash mismatch, file discarded")
            return 1
        tmp.replace(target)
        print(f"saved   {name}" + (f" (hash verified: {expected[:12]}...)" if expected else ""))
    print(f"\nModel ready in {DEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
