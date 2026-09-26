"""Bounded parsing and durable private files. Error codes never contain secrets."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat

REPO = 'pupkinson/SymphonyNext'
REPO_ID = 1381693716
APP_ID = 5069157
RULESET = 23980199
CHECK = 'symphony-next/verified-tests'
API = '/repos/' + REPO
SHA = re.compile(r'[0-9a-f]{40}')
MAX_JSON = 2 * 1024 * 1024

class Hold(Exception):
    """A stable, non-sensitive stop reason."""

def require(value, code):
    if not value: raise Hold(code)

def decode(raw):
    require(len(raw) <= MAX_JSON, 'json_size')
    def unique(pairs):
        out = {}
        for key, value in pairs:
            require(key not in out, 'duplicate_key')
            out[key] = value
        return out
    def invalid(_): raise Hold('nonfinite_json')
    try: return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid)
    except (ValueError, UnicodeError): raise Hold('invalid_json') from None

def sha256(raw): return hashlib.sha256(raw).hexdigest()

def blob_hash(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()

def canonical(data): return json.dumps(data, sort_keys=True, separators=(',', ':')).encode()

def trusted(path, private=False, directory=False):
    path = Path(path).absolute()
    for p in [path] + list(path.parents):
        s = p.lstat()
        require(s.st_uid == 0 and not s.st_mode & 0o022, 'untrusted_owner_or_mode')
        is_dir = p != path or directory
        require(stat.S_ISDIR(s.st_mode) if is_dir else stat.S_ISREG(s.st_mode), 'untrusted_type')
    if private: require(not path.stat().st_mode & 0o077, 'private_mode')
    return path

def write_new(path, data, mode=0o600):
    path=Path(path)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode)
    with os.fdopen(fd,'wb') as f:
        f.write(data);f.flush();os.fchmod(f.fileno(),mode);os.fsync(f.fileno())
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
