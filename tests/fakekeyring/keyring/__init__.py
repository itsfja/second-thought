"""A stand-in for the keyring package: keys come from FAKE_KEYCHAIN, a JSON object of name -> value, under service
"second-thought". FAKE_KEYCHAIN=broken makes every lookup fail, like a computer with no keychain."""
import json
import os


class NoKeyringError(RuntimeError):
    pass


def get_password(service, name):
    raw = os.environ.get("FAKE_KEYCHAIN", "{}")
    if raw == "broken":
        raise NoKeyringError("No recommended backend was available.")
    return json.loads(raw).get(name) if service == "second-thought" else None
