"""Static checks of bootstrap documentation bindings; no host/network/model calls.

These tests do not implement the separately blocked general package validator.
Run: python3 -B -m unittest discover -s tests -p test_bootstrap_snapshot.py -v
"""
import json
from pathlib import Path
import re
import shlex
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BootstrapSnapshotTests(unittest.TestCase):
    def text(self, path):
        file = ROOT / path
        self.assertTrue(file.is_file(), f"Missing snapshot file: {path}")
        return file.read_text(encoding="utf-8")

    def data(self, path):
        return json.loads(self.text(path))

    def test_workflow_repository_and_token(self):
        text = self.text("bootstrap/WORKFLOW.github.example.md")
        self.assertIn("repo: pupkinson/SymphonyNext\n", text)
        self.assertIn("token: $GITHUB_TOKEN\n", text)
        self.assertNotIn("pupkinson/symphony-next", text)
        self.assertNotIn("$SYMPHONY_NEXT_GITHUB_TOKEN", text)

    def test_clone_is_process_scoped(self):
        text = self.text("bootstrap/WORKFLOW.github.example.md")
        hook = re.search(r"  after_create: \|\n((?:    .*\n)+)", text)
        self.assertIsNotNone(hook)
        shell = "".join(line[4:] for line in hook.group(1).splitlines(True))
        result = subprocess.run(["/bin/bash", "-n"], input=shell, text=True,
                                capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        args = shlex.split(shell.replace("\\\n", ""))
        for token in ("GIT_SSH", "GIT_SSH_COMMAND", "GIT_CONFIG_COUNT",
                      "GIT_CONFIG_NOSYSTEM=1", "GIT_CONFIG_GLOBAL=/dev/null",
                      "GIT_TERMINAL_PROMPT=0", "--no-pager", "--template=",
                      "include.path=/etc/symphony-next-bootstrap/gitconfig",
                      "core.hooksPath=/dev/null", "core.fsmonitor=false",
                      "git@github.com:pupkinson/SymphonyNext.git"):
            self.assertIn(token, args)

    def test_example_does_not_grant_broad_sandbox(self):
        text = self.text("bootstrap/WORKFLOW.github.example.md")
        front = text.split("---", 2)[1]
        self.assertIn("thread_sandbox: workspace-write", front)
        self.assertNotIn("turn_sandbox_policy:", front)
        self.assertNotIn("networkAccess: true", front)
        self.assertNotIn("/home/programmer", front)
        self.assertIn("port: 4327", front)
        self.assertIn("host: 127.0.0.1", front)
        self.assertIn("not the installed workflow", text)

    def test_existing_installation_is_not_marked_missing(self):
        state = self.data("bootstrap/STATUS.json")
        self.assertTrue(state["owner_install"]["executed"])
        self.assertEqual(state["owner_install"]["uid"], 995)
        self.assertEqual(state["owner_install"]["gid"], 995)
        self.assertEqual(state["owner_install"]["status"], "INSTALLED_STOPPED")

    def test_runtime_observation_has_timestamp_and_no_live_claim(self):
        state = self.data("bootstrap/STATUS.json")
        self.assertIn("last_runtime_observation", state)
        observation = state["last_runtime_observation"]
        self.assertEqual(observation["captured_at"], "2026-09-22T15:17:00.471788+00:00")
        self.assertEqual(observation["active_state"], "inactive")
        self.assertEqual(observation["main_pid"], 0)
        self.assertFalse(observation["fresh_for_future_activation"])
        self.assertFalse(state["new_agent_started"])

    def test_binding_identity(self):
        bindings = self.data("bootstrap/RESOURCE_BINDINGS.json")
        self.assertEqual(bindings["repository"]["full_name"], "pupkinson/SymphonyNext")
        self.assertEqual(bindings["repository"]["id"], 1381693716)
        self.assertEqual(bindings["service"]["uid"], 995)
        self.assertEqual(bindings["github_api_token_env"], "GITHUB_TOKEN")
        self.assertEqual(bindings["codex_home"], "/var/lib/symphony-next-bootstrap/codex-home")

    def test_coolify_is_owner_reported_not_verified(self):
        bindings = self.data("bootstrap/RESOURCE_BINDINGS.json")
        coolify = bindings["coolify"]
        self.assertEqual(coolify["project_uuid"], "o1l7c2rybr9r2asqipcbedps")
        self.assertEqual(coolify["evidence_level"], "OWNER_REPORTED")
        self.assertFalse(coolify["live_readback_verified"])
        for name in ("application_uuid", "server_uuid", "destination_uuid", "domain"):
            self.assertIsNone(coolify[name])

    def test_policy_keeps_existing_limits_and_delegation(self):
        policy = self.data("policies/project-policy.json")
        self.assertIn("repository", policy)
        self.assertEqual(policy["repository"], "pupkinson/SymphonyNext")
        self.assertEqual(policy["repository_id"], 1381693716)
        self.assertEqual(policy["writer_slots"], 1)
        self.assertEqual(policy["bootstrap"]["restart"], "no")
        self.assertFalse(policy["bootstrap"]["start_enabled"])
        self.assertFalse(policy["github_actions_enabled"])
        self.assertFalse(policy["release"]["per_deploy_human_approval"])
        self.assertTrue(policy["release"]["requires_independent_review"])

    def test_historical_refusal_not_declared_resolved(self):
        state = self.data("bootstrap/STATUS.json")
        self.assertEqual(state["tests"]["server_package_validator"]["green"], "NOT_RUN")
        self.assertEqual(state["tests"]["server_package_validator"]["blocker"], "PUP-179")
        self.assertIn("history", state)
        self.assertEqual(state["history"]["original_package_commit"],
                         "2e68d041c2de03450a4735c3a560e1a8c165f342")
        self.assertEqual(state["history"]["platform_refusals"], "UNRESOLVED")

    def test_pilot_remains_unadmitted_and_separate(self):
        pilot = self.data("bootstrap/PILOT.json")
        self.assertEqual(pilot["id"], "BOOT-P01")
        self.assertFalse(pilot["admission"])
        self.assertEqual(pilot["allowed_output_files"], ["docs/pilots/BOOT-P01-report.md"])
        self.assertEqual(pilot["writer_slots"], 1)
        self.assertFalse(pilot["completes_SN_001"])
        self.assertEqual(pilot["model_turn"], "NOT_RUN")
        self.assertIn("tools/validate_package.py", pilot["excluded_paths"])

    def test_no_secret_literals_in_binding_material(self):
        for path in ("bootstrap/RESOURCE_BINDINGS.json", "bootstrap/PILOT.json",
                     "bootstrap/STATUS.json", "bootstrap/WORKFLOW.github.example.md"):
            text = self.text(path)
            self.assertNotRegex(text, r"github_pat_[A-Za-z0-9_]{20,}|ghp_[A-Za-z0-9]{20,}|-----BEGIN .*PRIVATE KEY")

    def test_agent_entry_allows_only_explicit_operational_pilot(self):
        text = self.text("AGENTS.md")
        self.assertIn("BOOT-P01", text)
        self.assertIn("bootstrap/PILOT.json", text)
        self.assertIn("not completion of SN-001", text)


if __name__ == "__main__":
    unittest.main()
