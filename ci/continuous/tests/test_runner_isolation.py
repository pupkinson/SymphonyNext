"""Characterize the observed Docker capability spelling without widening rights."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from snci import runner
from snci.common import Hold

KEY = "a" * 64
IMAGE = "sha256:" + "b" * 64
ROOT = Path("/var/lib/symphony-next-ci/prepare-main")


def container(capabilities):
    return {
        "Name": "/snci-" + KEY, "Image": IMAGE,
        "Config": {"User": "0:0", "Labels": {"snci.attempt": KEY},
                   "Entrypoint": ["/usr/bin/env"],
                   "Cmd": ["-i"] + runner.WORKER_ENV + ["/usr/bin/python3", "-I", "/worker.py"],
                   "Volumes": None, "OpenStdin": False, "Tty": False},
        "HostConfig": {
            "NetworkMode": "none", "ReadonlyRootfs": True, "Privileged": False,
            "RestartPolicy": {"Name": "no", "MaximumRetryCount": 0},
            "Memory": 4294967296, "MemorySwap": 4294967296,
            "NanoCpus": 2000000000, "PidsLimit": 256, "CapDrop": ["ALL"],
            "CapAdd": capabilities, "SecurityOpt": ["no-new-privileges:true"],
            "Tmpfs": {"/work": "rw,exec,nosuid,nodev,size=3g,uid=0,gid=0,mode=755",
                      "/tmp": "rw,exec,nosuid,nodev,size=256m,uid=0,gid=0,mode=1777"},
            "PidMode": "", "IpcMode": "private", "UTSMode": "", "UsernsMode": ""},
        "Mounts": [{"Type": "bind", "Source": str(source), "Destination": target,
                    "RW": False, "Propagation": "rprivate"} for source, target in
                   [(ROOT / "source", "/input"),
                    (Path("/opt/symphony-next-ci/worker.py"), "/worker.py"),
                    (ROOT / "source.json", "/source.json")]],
        "State": {"Status": "created", "Running": False}}


class RunnerIsolationTests(unittest.TestCase):
    def inspect(self, data):
        with patch.object(runner, "command", return_value=json.dumps([data]).encode()):
            return runner.inspect_container(KEY, IMAGE, ROOT)

    def test_observed_cap_prefixes_are_same_four_allowed_rights(self):
        data = container(["CAP_CHOWN", "CAP_KILL", "CAP_SETGID", "CAP_SETUID"])
        try:
            self.assertEqual(self.inspect(data), data)
        except Hold as error:
            self.fail("Observed safe Docker configuration was refused: " + str(error))

    def test_bare_and_mixed_prefix_spellings_preserve_exact_rights(self):
        for caps in (["SETUID", "CHOWN", "SETGID", "KILL"],
                     ["CAP_SETUID", "CHOWN", "CAP_SETGID", "KILL"]):
            with self.subTest(caps=caps):
                try:
                    self.inspect(container(caps))
                except Hold as error:
                    self.fail("Equivalent exact capability set refused: " + str(error))

    def test_extra_or_replacement_capability_remains_forbidden(self):
        for caps in (["CAP_CHOWN", "CAP_KILL", "CAP_SETGID", "CAP_SETUID", "CAP_SYS_ADMIN"],
                     ["CAP_CHOWN", "CAP_KILL", "CAP_SETUID", "CAP_SYS_ADMIN"],
                     ["CHOWN", "KILL", "SETGID", "SETUID", "SYS_ADMIN"]):
            with self.subTest(caps=caps), self.assertRaises(Hold):
                self.inspect(container(caps))

    def test_missing_duplicate_nested_prefix_or_case_change_is_forbidden(self):
        for caps in ([], ["CAP_CHOWN", "CAP_KILL", "CAP_SETGID"],
                     ["CAP_CHOWN", "CAP_KILL", "CAP_SETUID", "CAP_SETUID"],
                     ["CAP_CAP_CHOWN", "CAP_KILL", "CAP_SETGID", "CAP_SETUID"],
                     ["cap_chown", "CAP_KILL", "CAP_SETGID", "CAP_SETUID"]):
            with self.subTest(caps=caps), self.assertRaises(Hold):
                self.inspect(container(caps))

    def test_malformed_capabilities_fail_closed(self):
        for caps in (None, "CHOWN,KILL,SETGID,SETUID", [1, "KILL", "SETGID", "SETUID"],
                     {"CHOWN": True, "KILL": True, "SETGID": True, "SETUID": True}):
            with self.subTest(caps=caps):
                try:
                    self.inspect(container(caps))
                except Hold:
                    pass
                except Exception as error:
                    self.fail("Malformed capabilities need a stable hold: " + type(error).__name__)
                else:
                    self.fail("Malformed capabilities accepted")

    def test_other_isolation_gates_remain_required_with_cap_prefixes(self):
        original = container(["CAP_CHOWN", "CAP_KILL", "CAP_SETGID", "CAP_SETUID"])
        for field, value in (("NetworkMode", "host"), ("ReadonlyRootfs", False),
                             ("Privileged", True), ("CapDrop", []), ("SecurityOpt", []),
                             ("Memory", 0), ("PidsLimit", 0), ("Tmpfs", {})):
            data = copy.deepcopy(original); data["HostConfig"][field] = value
            with self.subTest(field=field), self.assertRaises(Hold):
                self.inspect(data)


if __name__ == "__main__":
    unittest.main()
