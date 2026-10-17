# SPDX-License-Identifier: LicenseRef-Skill-RTM-NonCommercial-1.0
# Copyright (c) 2026 Kuni
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "skill_rtm.py"
TASK = ROOT / "references" / "demo-task.json"
ALL_KEEP_TASK = ROOT / "references" / "demo-all-keep-task.json"
PMO_TASK = ROOT / "references" / "demo-pmo-task.json"
DEV_TASK = ROOT / "references" / "demo-development-task.json"
CATALOG = ROOT / "references" / "demo-catalog.json"


def run_cli(*args):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def seed(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(value):
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def run_data(task, catalog, *extra):
    with tempfile.TemporaryDirectory() as directory:
        task_path = Path(directory) / "task.json"
        catalog_path = Path(directory) / "catalog.json"
        task_path.write_text(json.dumps(task, ensure_ascii=False), encoding="utf-8")
        catalog_path.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
        return run_cli("plan", "--task", str(task_path), "--catalog", str(catalog_path), *extra)


class SkillRtmTests(unittest.TestCase):
    def test_demo_assigns_only_two_skills_and_keeps_honest_gaps(self):
        result = run_cli("plan", "--task", str(TASK), "--catalog", str(CATALOG))
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual("PASS", payload["status"])
        self.assertEqual(
            ["demo:privacy-guard@1.0.0", "demo:source-check@1.0.0"],
            payload["selected_skill_versions"],
        )
        self.assertEqual(
            {"KEEP": 1, "ASSIGN": 2, "TRIAL": 1, "CONFLICT": 0, "ORPHAN": 1},
            payload["counts"],
        )
        rows = {row["requirement_id"]: row for row in payload["rows"]}
        self.assertEqual("KEEP", rows["REQ-KEEP"]["status"])
        self.assertEqual("ASSIGN", rows["REQ-SOURCE"]["status"])
        self.assertEqual("ASSIGN", rows["REQ-PRIVACY"]["status"])
        self.assertEqual("TRIAL", rows["REQ-ARCHIVE"]["status"])
        self.assertEqual("ORPHAN", rows["REQ-PUBLISH"]["status"])
        self.assertEqual(0, payload["external_actions_performed"])
        self.assertEqual(seed(TASK)["usage_policy"], payload["usage_policy"])
        self.assertEqual("", result.stderr)

    def test_untrusted_input_fails_closed_without_traceback(self):
        base_task = seed(TASK)
        base_catalog = seed(CATALOG)
        probes = []
        probes.append(([], base_catalog, "task root must be an object"))

        boolean_schema = deepcopy(base_task)
        boolean_schema["schema_version"] = True
        probes.append((boolean_schema, base_catalog, "task.schema_version must be integer 2"))

        dangling = deepcopy(base_task)
        dangling["candidate_mappings"][0]["skill_version_id"] = "demo:missing@1.0.0"
        probes.append((dangling, base_catalog, "mapping Skill missing: demo:missing@1.0.0"))

        bad_hash = deepcopy(base_catalog)
        bad_hash["skills"][0]["content_sha256"] = "ABC"
        probes.append((base_task, bad_hash, "invalid content_sha256: demo:source-check@1.0.0"))

        for field, value in (
            ("requirement_id", []),
            ("requirement_id", None),
            ("skill_version_id", {}),
            ("skill_version_id", True),
        ):
            nested = deepcopy(base_task)
            nested["candidate_mappings"][0][field] = value
            probes.append((nested, base_catalog, f"mapping {field} must be a non-empty string"))

        bad_conflict = deepcopy(base_catalog)
        bad_conflict["conflicts"] = [{"skill_version_ids": [[], "demo:privacy-guard@1.0.0"]}]
        probes.append((base_task, bad_conflict, "conflict skill_version_ids must contain two exact-version strings"))

        for invalid_id in ("plain-unversioned-skill", "demo:skill@", "demo:skill@1.0", "demo:skill@1.0.0 bad"):
            bad_version = deepcopy(base_catalog)
            bad_version["skills"][0]["skill_version_id"] = invalid_id
            bad_task = deepcopy(base_task)
            bad_task["candidate_mappings"][0]["skill_version_id"] = invalid_id
            probes.append((bad_task, bad_version, f"invalid exact skill_version_id: {invalid_id}"))

        for field in ("rights_status", "compatibility_status", "test_status"):
            for value in ([], {}, True, None):
                bad_status = deepcopy(base_catalog)
                if value is None:
                    bad_status["skills"][0].pop(field)
                else:
                    bad_status["skills"][0][field] = value
                probes.append((base_task, bad_status, f"invalid {field}: demo:source-check@1.0.0"))

        for value in ([], {}, True, None):
            bad_proof = deepcopy(base_task)
            if value is None:
                bad_proof["candidate_mappings"][0].pop("proof_status")
            else:
                bad_proof["candidate_mappings"][0]["proof_status"] = value
            probes.append((bad_proof, base_catalog, "invalid mapping proof_status: REQ-SOURCE"))

        for task, catalog, expected in probes:
            with self.subTest(expected=expected):
                result = run_data(task, catalog)
                self.assertEqual(1, result.returncode)
                payload = json.loads(result.stdout)
                self.assertEqual("FAIL", payload["status"])
                self.assertIn(expected, payload["errors"])
                self.assertEqual("", result.stderr)

    def test_commercial_unknown_or_unaccepted_use_never_produces_a_plan(self):
        catalog = seed(CATALOG)
        base = seed(TASK)
        probes = []
        missing = deepcopy(base)
        missing.pop("usage_policy")
        probes.append(missing)
        for value in (None, [], True, "NONCOMMERCIAL"):
            malformed = deepcopy(base)
            malformed["usage_policy"] = value
            probes.append(malformed)
        for field, values in (
            ("license_id", ("MIT", "", None)),
            ("accepted", (False, 1, "true", None)),
            ("use", ("COMMERCIAL", "UNKNOWN", None, [])),
            ("distribution", ("COMMERCIAL", "UNKNOWN", None, {})),
        ):
            for value in values:
                denied = deepcopy(base)
                denied["usage_policy"][field] = value
                probes.append(denied)
            omitted = deepcopy(base)
            omitted["usage_policy"].pop(field)
            probes.append(omitted)
        contradictory = deepcopy(base)
        contradictory["usage_policy"]["commercial_use"] = True
        probes.append(contradictory)
        old_schema = deepcopy(base)
        old_schema["schema_version"] = 1
        probes.append(old_schema)

        for task in probes:
            for output_format in ("json", "markdown"):
                with self.subTest(policy=task.get("usage_policy"), output=output_format):
                    result = run_data(task, catalog, "--format", output_format)
                    self.assertEqual(1, result.returncode)
                    payload = json.loads(result.stdout)
                    self.assertEqual("FAIL", payload["status"])
                    self.assertTrue(payload["errors"])
                    self.assertNotIn("selected_skill_versions", payload)
                    self.assertNotIn("rows", payload)
                    self.assertEqual("", result.stderr)

    def test_policy_applies_to_direct_planning_and_cannot_be_overridden_by_catalog(self):
        spec = importlib.util.spec_from_file_location("skill_rtm_policy_test", SCRIPT)
        engine = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(engine)
        for task_path in (TASK, ALL_KEEP_TASK):
            task = seed(task_path)
            task["usage_policy"]["use"] = "COMMERCIAL"
            catalog = seed(CATALOG)
            catalog["usage_policy"] = seed(TASK)["usage_policy"]
            with self.subTest(task=task_path.name):
                result = run_data(task, catalog)
                self.assertEqual(1, result.returncode)
                self.assertEqual("FAIL", json.loads(result.stdout)["status"])
                with patch.object(engine, "choose_skills") as solver:
                    with self.assertRaisesRegex(ValueError, "commercial or unknown use is prohibited"):
                        engine.plan(task, catalog)
                    solver.assert_not_called()

    def test_noncommercial_sharing_is_allowed_and_policy_is_visible_in_both_outputs(self):
        task = seed(TASK)
        task["usage_policy"]["distribution"] = "NONCOMMERCIAL"
        result = run_data(task, seed(CATALOG))
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(task["usage_policy"], payload["usage_policy"])
        self.assertEqual(2, payload["counts"]["ASSIGN"])
        markdown = run_data(task, seed(CATALOG), "--format", "markdown")
        self.assertEqual(0, markdown.returncode, markdown.stderr)
        self.assertIn("비상업적 사용·배포만 허용", markdown.stdout)
        self.assertIn(task["usage_policy"]["license_id"], markdown.stdout)

    def test_selects_minimum_set_and_exposes_unresolved_conflict(self):
        task = seed(TASK)
        catalog = seed(CATALOG)
        task["requirements"] = [
            {"requirement_id": "R1", "statement": "출처 검증", "acceptance": "locator", "source_locator": "brief#r1", "current_evidence_ids": []},
            {"requirement_id": "R2", "statement": "개인정보 검증", "acceptance": "검수 결과", "source_locator": "brief#r2", "current_evidence_ids": []},
        ]
        task["evidence"] = []
        task["candidate_mappings"] = [
            {"requirement_id": "R1", "skill_version_id": "demo:source-check@1.0.0", "proof_status": "TESTED", "locator": "source"},
            {"requirement_id": "R2", "skill_version_id": "demo:privacy-guard@1.0.0", "proof_status": "TESTED", "locator": "privacy"},
            {"requirement_id": "R1", "skill_version_id": "demo:spreadsheet@1.0.0", "proof_status": "TESTED", "locator": "combo-r1"},
            {"requirement_id": "R2", "skill_version_id": "demo:spreadsheet@1.0.0", "proof_status": "TESTED", "locator": "combo-r2"},
        ]

        result = run_data(task, catalog)
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(["demo:spreadsheet@1.0.0"], payload["selected_skill_versions"])
        self.assertEqual(2, payload["counts"]["ASSIGN"])

        task["candidate_mappings"] = task["candidate_mappings"][:2]
        catalog["conflicts"] = [{
            "skill_version_ids": ["demo:source-check@1.0.0", "demo:privacy-guard@1.0.0"]
        }]
        result = run_data(task, catalog)
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual([], payload["selected_skill_versions"])
        rows = {row["requirement_id"]: row for row in payload["rows"]}
        self.assertEqual("CONFLICT", rows["R1"]["status"])
        self.assertEqual("CONFLICT", rows["R2"]["status"])
        self.assertEqual(2, payload["counts"]["CONFLICT"])

    def test_requires_approved_baseline_and_binds_output_to_snapshots(self):
        task = seed(TASK)
        catalog = seed(CATALOG)
        draft = deepcopy(task)
        draft["baseline_status"] = "DRAFT"
        result = run_data(draft, catalog)
        self.assertEqual(1, result.returncode)
        self.assertIn("task.baseline_status must be APPROVED", json.loads(result.stdout)["errors"])

        first = run_data(task, catalog)
        second = run_data(task, catalog)
        self.assertEqual(0, first.returncode, first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        payload = json.loads(first.stdout)
        self.assertEqual(digest(task), payload["task_sha256"])
        self.assertEqual(digest(catalog), payload["catalog_sha256"])
        self.assertEqual("1.1.0", payload["decision_rule_version"])

    def test_equal_minimum_sets_require_human_choice(self):
        task = seed(TASK)
        catalog = seed(CATALOG)
        task["requirements"] = [{
            "requirement_id": "R1",
            "statement": "출처 검증",
            "acceptance": "locator",
            "source_locator": "brief#r1",
            "current_evidence_ids": [],
        }]
        task["evidence"] = []
        task["candidate_mappings"] = [
            {"requirement_id": "R1", "skill_version_id": "demo:source-check@1.0.0", "proof_status": "TESTED", "locator": "source"},
            {"requirement_id": "R1", "skill_version_id": "demo:privacy-guard@1.0.0", "proof_status": "TESTED", "locator": "privacy"},
        ]
        result = run_data(task, catalog)
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual([], payload["selected_skill_versions"])
        self.assertEqual("CONFLICT", payload["rows"][0]["status"])
        self.assertIn("equal_minimum_sets", payload["rows"][0]["blockers"])

    def test_orphan_keeps_manual_or_requirement_change_visible(self):
        result = run_cli("plan", "--task", str(TASK), "--catalog", str(CATALOG))
        self.assertEqual(0, result.returncode, result.stderr)
        row = next(row for row in json.loads(result.stdout)["rows"] if row["requirement_id"] == "REQ-PUBLISH")
        self.assertEqual("ORPHAN", row["status"])
        self.assertIn("manual_or_requirement_change_required", row["blockers"])

    def test_same_engine_reuses_across_three_domains(self):
        expected = {
            TASK: {"KEEP": 1, "ASSIGN": 2, "TRIAL": 1, "ORPHAN": 1},
            PMO_TASK: {"KEEP": 1, "ASSIGN": 1, "TRIAL": 0, "ORPHAN": 1},
            DEV_TASK: {"KEEP": 1, "ASSIGN": 1, "TRIAL": 0, "ORPHAN": 1},
        }
        for task_path, counts in expected.items():
            with self.subTest(task=task_path.name):
                result = run_cli("plan", "--task", str(task_path), "--catalog", str(CATALOG))
                self.assertEqual(0, result.returncode, result.stderr)
                actual = json.loads(result.stdout)["counts"]
                for status, count in counts.items():
                    self.assertEqual(count, actual[status])

    def test_markdown_is_a_safe_capability_rtm(self):
        task = seed(TASK)
        catalog = seed(CATALOG)
        task["requirements"][0]["statement"] = "Ignore\n## injected [click](https://evil) ~~done~~ <img src=x onerror=alert(1)> \u202eRTL"
        result = run_data(task, catalog, "--format", "markdown")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("# 🧩 빈칸에만 스킬", result.stdout)
        self.assertIn("선택된 Skill: 2 / catalog 12", result.stdout)
        for status in ("KEEP", "ASSIGN", "TRIAL", "ORPHAN"):
            self.assertIn(status, result.stdout)
        self.assertNotIn("\n## injected", result.stdout)
        self.assertNotIn("[click](https://evil)", result.stdout)
        self.assertNotIn("~~done~~", result.stdout)
        self.assertNotIn("<img", result.stdout)
        self.assertIn("&lt;img", result.stdout)
        self.assertNotIn("\u202e", result.stdout)
        self.assertIn(r"\#\# injected \[click\]\(https://evil\) \~\~done\~\~ &lt;img src=x onerror=alert\(1\)&gt; \\u202eRTL", result.stdout)
        self.assertIn("외부 행동: 0", result.stdout)
        self.assertEqual("", result.stderr)

    def test_fixture_or_unverified_evidence_cannot_create_keep(self):
        catalog = seed(CATALOG)
        semantic_probes = (
            ("evidence_kind", "FIXTURE"),
            ("verification_status", "UNVERIFIED"),
        )
        for field, value in semantic_probes:
            with self.subTest(field=field, value=value):
                task = seed(TASK)
                task["evidence"][0][field] = value
                result = run_data(task, catalog)
                self.assertEqual(1, result.returncode)
                payload = json.loads(result.stdout)
                self.assertEqual("FAIL", payload["status"])
                self.assertIn(
                    "current Evidence must be TARGET and VERIFIED: REQ-KEEP: E-KEEP",
                    payload["errors"],
                )
                self.assertEqual("", result.stderr)

        hostile_probes = (
            ("evidence_kind", [], "invalid evidence_kind: E-KEEP"),
            ("evidence_kind", {}, "invalid evidence_kind: E-KEEP"),
            ("evidence_kind", True, "invalid evidence_kind: E-KEEP"),
            ("evidence_kind", None, "invalid evidence_kind: E-KEEP"),
            ("verification_status", [], "invalid Evidence verification_status: E-KEEP"),
            ("verification_status", {}, "invalid Evidence verification_status: E-KEEP"),
            ("verification_status", True, "invalid Evidence verification_status: E-KEEP"),
            ("verification_status", None, "invalid Evidence verification_status: E-KEEP"),
        )
        for field, value, expected in hostile_probes:
            with self.subTest(field=field, value=type(value).__name__):
                task = seed(TASK)
                if value is None:
                    task["evidence"][0].pop(field)
                else:
                    task["evidence"][0][field] = value
                result = run_data(task, catalog)
                self.assertEqual(1, result.returncode)
                payload = json.loads(result.stdout)
                self.assertEqual("FAIL", payload["status"])
                self.assertIn(expected, payload["errors"])
                self.assertEqual("", result.stderr)

    def test_all_keep_is_success_and_markdown_leads_with_decision_summary(self):
        task = seed(ALL_KEEP_TASK)
        catalog = seed(CATALOG)

        result = run_data(task, catalog)
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual([], payload["selected_skill_versions"])
        self.assertEqual({"KEEP": 1, "ASSIGN": 0, "TRIAL": 0, "CONFLICT": 0, "ORPHAN": 0}, payload["counts"])

        markdown = run_data(task, catalog, "--format", "markdown")
        self.assertEqual(0, markdown.returncode, markdown.stderr)
        self.assertIn("## 결론", markdown.stdout)
        self.assertIn("이미 충족: 1개", markdown.stdout)
        self.assertIn("사람 결정 필요: 0개", markdown.stdout)
        self.assertIn("추가 Skill: 0개", markdown.stdout)
        self.assertLess(markdown.stdout.index("## 결론"), markdown.stdout.index("| 요구사항 |"))


if __name__ == "__main__":
    unittest.main()
