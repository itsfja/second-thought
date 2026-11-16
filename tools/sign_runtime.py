#!/usr/bin/env python3
"""Signs a release's runtime.py with an Ed25519 key kept off GitHub (#311, #429).

    python tools/sign_runtime.py --make-key sign-key.pem spare-key.pem   # once: the working key and the spare
    python tools/sign_runtime.py sign-key.pem runtime.py                # writes runtime.py.sig, and the gh command

The runtime holds both public halves (UPDATE_SIGNING_KEY and UPDATE_SIGNING_SPARE_KEY in
python/second_thought/update.py) and accepts a release signed by either, so a key can be retired by dropping it
from the next release's runtime (SECURITY.md says how): keep the spare's private half somewhere else. Put the two
hex strings in update.py before the first signed release, and mention it in CHANGELOG.md under Security. The private
keys never leave your computer: GitHub can publish a release, but it can't make a signature this program's
--update-runtime will accept. Uses openssl, which installs nothing here.
"""
import base64
import pathlib
import subprocess
import sys


def run(args):
    out = subprocess.run(args, capture_output=True, check=True)
    return out.stdout


def make_key(path):
    if path.exists():
        sys.exit(f"{path} already exists, so nothing was written.")
    run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", str(path)])
    return run(["openssl", "pkey", "-in", str(path), "-pubout", "-outform", "DER"])[-32:].hex()


def main():
    if sys.argv[1:2] == ["--make-key"] and len(sys.argv) in (3, 4):
        working, spare = pathlib.Path(sys.argv[2]), (pathlib.Path(sys.argv[3]) if len(sys.argv) == 4 else None)
        pub = make_key(working)
        print(f"Made {working}. Its public half, to put in UPDATE_SIGNING_KEY in python/second_thought/update.py:\n\n"
              f"UPDATE_SIGNING_KEY = \"{pub}\"\n")
        if spare:
            print(f"Made {spare}. Its public half, to put in UPDATE_SIGNING_SPARE_KEY (keep the key itself somewhere "
                  f"else, so the working key can be retired):\n\nUPDATE_SIGNING_SPARE_KEY = \"{make_key(spare)}\"\n")
        else:
            print("Make a spare too, with:  python tools/sign_runtime.py --make-key sign-key.pem spare-key.pem")
        print("\nKeep the keys off GitHub: not in this repository, not in Actions.")
        return
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    key, runtime = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
    if not key.is_file() or not runtime.is_file():
        sys.exit("Give an existing key file and the runtime.py to sign.")
    sig = run(["openssl", "pkeyutl", "-sign", "-inkey", str(key), "-rawin", "-in", str(runtime)])
    out = runtime.with_suffix(runtime.suffix + ".sig")
    out.write_text(base64.b64encode(sig).decode() + "\n", encoding="utf-8")
    print(f"Wrote {out} ({len(sig)} bytes, base64). Attach it to the release:\n\n"
          f"gh release upload {runtime.parent.name if runtime.parent.name.startswith('v') else 'TAG'} {out} --clobber --repo itsfja/second-thought")


if __name__ == "__main__":
    main()
