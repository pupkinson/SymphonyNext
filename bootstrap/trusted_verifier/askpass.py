#!/usr/bin/python3
"""Git-only password helper; its stdout goes to Git, never the operator log."""
import os
from pathlib import Path
import sys

if os.geteuid() != 0 or len(sys.argv) != 2:
    raise SystemExit(2)
question = sys.argv[1].lower()
if 'username' in question:
    print('x-access-token')
elif 'password' in question:
    expected = '/var/lib/symphony-next-verifier/private/checkout-token'
    if os.environ.get('SNV_TOKEN_FILE') != expected:
        raise SystemExit(2)
    print(Path(expected).read_text())
else:
    raise SystemExit(2)
