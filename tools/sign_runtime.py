#!/usr/bin/env python3
"""Signs a release's runtime.py with an Ed25519 key kept off GitHub (#311).

    python tools/sign_runtime.py --make-key sign-key.pem   # once: a new key, and its public half, as hex
    python tools/sign_runtime.py sign-key.pem runtime.py   # writes runtime.py.sig beside it, and the gh command

The private key never leaves your computer: GitHub can publish a release, but it can't make a signature this
program's --update-runtime will accept, since the runtime holds the public half (UPDATE_SIGNING_KEY in
python/second_thought/update.py). Put that hex string there before the first signed release, and mention it in
CHANGELOG.md under Security. Uses openssl, which installs nothing here.
"""
import base64
import pathlib
import subprocess
import sys


def run(args):
    out = subprocess.run(args, capture_output=True, check=True)
    return out.stdout


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--make-key":
        key = pathlib.Path(sys.argv[2])
        if key.exists():
            sys.exit(f"{key} already exists, so nothing was written.")
        run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", str(key)])
        pub = run(["openssl", "pkey", "-in", str(key), "-pubout", "-outform", "DER"])[-32:]
        print(f"Made {key}. Its public half, to put in UPDATE_SIGNING_KEY in python/second_thought/update.py:\n\n"
              f"UPDATE_SIGNING_KEY = \"{pub.hex()}\"\n\nKeep the key off GitHub: not in this repository, not in Actions.")
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
