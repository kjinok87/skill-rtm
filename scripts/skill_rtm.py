import argparse
import hashlib
import html
import itertools
import json
import re
import sys
import unicodedata
from pathlib import Path

STATUSES = ("KEEP", "ASSIGN", "TRIAL", "CONFLICT", "ORPHAN")
EXACT_SKILL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]*@(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?\Z")


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def canonical_digest(value):
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate(task, catalog):
    errors = []
    if not isinstance(task, dict):
        return ["task root must be an object"]
    if not isinstance(catalog, dict):
        return ["catalog root must be an object"]
    if type(task.get("schema_version")) is not int or task.get("schema_version") != 1:
        errors.append("task.schema_version must be integer 1")
    if type(catalog.get("schema_version")) is not int or catalog.get("schema_version") != 1:
        errors.append("catalog.schema_version must be integer 1")
    if task.get("baseline_status") != "APPROVED":
        errors.append("task.baseline_status must be APPROVED")
    for field in ("task_id", "revision"):
        if not nonempty(task.get(field)):
            errors.append(f"task.{field} must be a non-empty string")
    for field in ("catalog_id", "catalog_revision", "catalog_source"):
        if not nonempty(catalog.get(field)):
            errors.append(f"catalog.{field} must be a non-empty string")

    collections = (
        (task, "requirements", "task.requirements"),
        (task, "evidence", "task.evidence"),
        (task, "candidate_mappings", "task.candidate_mappings"),
        (catalog, "skills", "catalog.skills"),
        (catalog, "conflicts", "catalog.conflicts"),
    )
    for owner, key, label in collections:
        if not isinstance(owner.get(key), list):
            errors.append(f"{label} must be a list")
    if errors:
        return errors

    for label, rows in (
        ("requirement", task["requirements"]),
        ("evidence", task["evidence"]),
        ("mapping", task["candidate_mappings"]),
        ("skill", catalog["skills"]),
        ("conflict", catalog["conflicts"]),
    ):
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                errors.append(f"{label}[{index}] must be an object")
    if errors:
        return errors

    def ids(rows, key, label):
        values = set()
        for row in rows:
            value = row.get(key)
            if not nonempty(value):
                errors.append(f"{label} must be a non-empty string")
                continue
            elif value in values:
                errors.append(f"duplicate {label}: {value}")
            else:
                values.add(value)
        return values

    requirement_ids = ids(task["requirements"], "requirement_id", "requirement_id")
    evidence_ids = ids(task["evidence"], "evidence_id", "evidence_id")
    skill_ids = ids(catalog["skills"], "skill_version_id", "skill_version_id")
    evidence_by_id = {
        row["evidence_id"]: row
        for row in task["evidence"]
        if nonempty(row.get("evidence_id"))
    }

    for row in task["requirements"]:
        if not nonempty(row.get("statement")):
            errors.append("requirement statement must be a non-empty string")
        if not nonempty(row.get("acceptance")):
            errors.append("requirement acceptance must be a non-empty string")
        if not nonempty(row.get("source_locator")):
            errors.append(f"requirement source_locator missing: {row.get('requirement_id')}")
        current = row.get("current_evidence_ids")
        if not isinstance(current, list) or any(not nonempty(item) for item in current):
            errors.append(f"current_evidence_ids must be a list of strings: {row.get('requirement_id')}")
        elif any(item not in evidence_ids for item in current):
            errors.append(f"current Evidence missing: {row.get('requirement_id')}")
        else:
            for item in current:
                evidence_row = evidence_by_id[item]
                if evidence_row.get("evidence_kind") != "TARGET" or evidence_row.get("verification_status") != "VERIFIED":
                    errors.append(
                        f"current Evidence must be TARGET and VERIFIED: {row.get('requirement_id')}: {item}"
                    )

    for row in task["evidence"]:
        if not nonempty(row.get("locator")):
            errors.append(f"Evidence locator missing: {row.get('evidence_id')}")
        if not isinstance(row.get("evidence_kind"), str) or row.get("evidence_kind") not in {"TARGET", "FIXTURE"}:
            errors.append(f"invalid evidence_kind: {row.get('evidence_id')}")
        if not isinstance(row.get("verification_status"), str) or row.get("verification_status") not in {"VERIFIED", "UNVERIFIED"}:
            errors.append(f"invalid Evidence verification_status: {row.get('evidence_id')}")

    for row in catalog["skills"]:
        skill_id = row.get("skill_version_id")
        if nonempty(skill_id) and not EXACT_SKILL_ID.fullmatch(skill_id):
            errors.append(f"invalid exact skill_version_id: {skill_id}")
        digest = row.get("content_sha256")
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            errors.append(f"invalid content_sha256: {skill_id}")
        for field, allowed in (
            ("rights_status", {"CLEARED", "UNKNOWN"}),
            ("compatibility_status", {"VERIFIED", "UNKNOWN"}),
            ("test_status", {"PASS", "FAIL", "NOT_RUN"}),
        ):
            if not isinstance(row.get(field), str) or row.get(field) not in allowed:
                errors.append(f"invalid {field}: {skill_id}")

    for row in task["candidate_mappings"]:
        requirement_id = row.get("requirement_id")
        skill_id = row.get("skill_version_id")
        if not nonempty(requirement_id):
            errors.append("mapping requirement_id must be a non-empty string")
        elif requirement_id not in requirement_ids:
            errors.append(f"mapping Requirement missing: {requirement_id}")
        if not nonempty(skill_id):
            errors.append("mapping skill_version_id must be a non-empty string")
        elif skill_id not in skill_ids:
            errors.append(f"mapping Skill missing: {skill_id}")
        if not isinstance(row.get("proof_status"), str) or row.get("proof_status") not in {"TESTED", "DECLARED"}:
            errors.append(f"invalid mapping proof_status: {requirement_id}")
        if not nonempty(row.get("locator")):
            errors.append(f"mapping locator missing: {requirement_id}")

    for row in catalog["conflicts"]:
        pair = row.get("skill_version_ids")
        if not isinstance(pair, list) or len(pair) != 2 or any(not nonempty(item) for item in pair):
            errors.append("conflict skill_version_ids must contain two exact-version strings")
        elif pair[0] == pair[1]:
            errors.append("conflict skill_version_ids must contain two distinct IDs")
        elif any(item not in skill_ids for item in pair):
            errors.append("conflict Skill missing")
    return sorted(set(errors))


def fail(errors):
    json.dump({"status": "FAIL", "errors": errors}, sys.stdout, ensure_ascii=False, sort_keys=True)
    sys.stdout.write("\n")
    return 1


def markdown_escape(value):
    safe = []
    for character in " ".join(str(value).splitlines()):
        code = ord(character)
        if unicodedata.category(character) == "Cf" or code < 32 or 127 <= code <= 159:
            safe.append(f"\\u{code:04x}")
        else:
            safe.append(character)
    text = html.escape("".join(safe), quote=False)
    for marker in ("\\", "`", "*", "_", "{", "}", "[", "]", "(", ")", "#", "+", "-", ".", "!", "|", ">", "~"):
        text = text.replace(marker, "\\" + marker)
    return text


def render_markdown(task, catalog, payload):
    requirements = {row["requirement_id"]: row for row in task["requirements"]}
    unresolved = sum(payload["counts"][status] for status in ("TRIAL", "CONFLICT", "ORPHAN"))
    lines = [
        "# 🧩 빈칸에만 스킬",
        "",
        f"- Task: `{markdown_escape(payload['task_id'])}` / `{markdown_escape(payload['revision'])}`",
        f"- 선택된 Skill: {len(payload['selected_skill_versions'])} / catalog {len(catalog['skills'])}",
        f"- 외부 행동: {payload['external_actions_performed']}",
        "",
        "## 결론",
        "",
        f"- 이미 충족: {payload['counts']['KEEP']}개",
        f"- 사람 결정 필요: {unresolved}개",
        f"- 추가 Skill: {len(payload['selected_skill_versions'])}개",
        "- 다음: " + (
            "추가 Skill 없이 현재 절차를 유지합니다."
            if not payload["selected_skill_versions"] and not unresolved
            else "아래 빈칸과 배정안을 검토합니다. 설치·실행은 별도 승인입니다."
        ),
        "",
        "| 요구사항 | 상태 | 요구 | 담당·근거·막힘 |",
        "|---|---|---|---|",
    ]
    for row in payload["rows"]:
        requirement = requirements[row["requirement_id"]]
        detail = row.get("skill_version_id") or ", ".join(row.get("evidence", []) or row["blockers"]) or "-"
        lines.append(
            f"| `{markdown_escape(row['requirement_id'])}` | **{row['status']}** | "
            f"{markdown_escape(requirement['statement'])} | {markdown_escape(detail)} |"
        )
    return "\n".join(lines) + "\n"


def gate_blockers(skill, mapping):
    checks = (
        (skill["rights_status"] == "CLEARED", "rights_not_cleared"),
        (skill["compatibility_status"] == "VERIFIED", "compatibility_not_verified"),
        (skill["test_status"] == "PASS", "tests_not_passed"),
        (mapping["proof_status"] == "TESTED", "mapping_not_tested"),
    )
    return [reason for passed, reason in checks if not passed]


def choose_skills(task, catalog, skills, mappings):
    coverage = {}
    kept = {row["requirement_id"] for row in task["requirements"] if row["current_evidence_ids"]}
    for requirement_id, candidates in mappings.items():
        if requirement_id in kept:
            continue
        for mapping in candidates:
            skill_id = mapping["skill_version_id"]
            if not gate_blockers(skills[skill_id], mapping):
                coverage.setdefault(skill_id, set()).add(requirement_id)

    candidate_ids = sorted(coverage)
    if len(candidate_ids) > 20:
        raise ValueError("more than 20 mapped eligible Skills")  # ponytail: exact search; shortlist upstream.
    conflicts = {
        frozenset(item["skill_version_ids"])
        for item in catalog["conflicts"]
    }
    choices = []
    for size in range(len(candidate_ids) + 1):
        for combo in itertools.combinations(candidate_ids, size):
            if any(frozenset(pair) in conflicts for pair in itertools.combinations(combo, 2)):
                continue
            covered = set().union(*(coverage[item] for item in combo)) if combo else set()
            choices.append((-len(covered), len(combo), combo))
    best_key = min((choice[0], choice[1]) for choice in choices)
    best_combos = [set(choice[2]) for choice in choices if choice[:2] == best_key]
    selected = set.intersection(*best_combos) if best_combos else set()
    ambiguous = set.union(*best_combos) - selected if len(best_combos) > 1 else set()
    return selected, conflicts, ambiguous


def plan(task, catalog):
    skills = {item["skill_version_id"]: item for item in catalog["skills"]}
    evidence = {item["evidence_id"]: item for item in task["evidence"]}
    mappings = {}
    for item in task["candidate_mappings"]:
        mappings.setdefault(item["requirement_id"], []).append(item)
    selected, conflicts, ambiguous = choose_skills(task, catalog, skills, mappings)

    rows = []
    for requirement in task["requirements"]:
        requirement_id = requirement["requirement_id"]
        current = requirement["current_evidence_ids"]
        if current:
            rows.append({
                "requirement_id": requirement_id,
                "status": "KEEP",
                "evidence": [evidence[item]["locator"] for item in current],
                "blockers": [],
            })
            continue

        candidates = mappings.get(requirement_id, [])
        eligible = []
        blocked = []
        for mapping in candidates:
            skill = skills[mapping["skill_version_id"]]
            blockers = gate_blockers(skill, mapping)
            if blockers:
                blocked.extend(blockers)
            else:
                eligible.append(mapping)

        assigned = [item for item in eligible if item["skill_version_id"] in selected]
        if assigned:
            chosen = min(assigned, key=lambda item: item["skill_version_id"])
            rows.append({
                "requirement_id": requirement_id,
                "status": "ASSIGN",
                "skill_version_id": chosen["skill_version_id"],
                "locator": chosen["locator"],
                "blockers": [],
            })
        elif eligible:
            blocked_pairs = [
                sorted((item["skill_version_id"], selected_id))
                for item in eligible
                for selected_id in selected
                if frozenset((item["skill_version_id"], selected_id)) in conflicts
            ]
            blockers = ["skill_conflict:" + ":".join(pair) for pair in sorted(blocked_pairs)]
            if any(item["skill_version_id"] in ambiguous for item in eligible):
                blockers.append("equal_minimum_sets")
            rows.append({
                "requirement_id": requirement_id,
                "status": "CONFLICT",
                "blockers": blockers,
            })
        elif candidates:
            rows.append({
                "requirement_id": requirement_id,
                "status": "TRIAL",
                "blockers": sorted(set(blocked)),
            })
        else:
            rows.append({
                "requirement_id": requirement_id,
                "status": "ORPHAN",
                "blockers": ["no_candidate_mapping", "manual_or_requirement_change_required"],
            })

    counts = {status: 0 for status in STATUSES}
    for row in rows:
        counts[row["status"]] += 1
    return {
        "status": "PASS",
        "decision_rule_version": "1.1.0",
        "task_id": task["task_id"],
        "revision": task["revision"],
        "task_sha256": canonical_digest(task),
        "catalog_id": catalog["catalog_id"],
        "catalog_revision": catalog["catalog_revision"],
        "catalog_sha256": canonical_digest(catalog),
        "selected_skill_versions": sorted(selected),
        "rows": rows,
        "counts": counts,
        "external_actions_performed": 0,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    command = subparsers.add_parser("plan")
    command.add_argument("--task", required=True)
    command.add_argument("--catalog", required=True)
    command.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args(argv)
    try:
        task = load(args.task)
        catalog = load(args.catalog)
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as error:
        return fail([f"invalid input: {type(error).__name__}"])
    errors = validate(task, catalog)
    if errors:
        return fail(errors)
    try:
        payload = plan(task, catalog)
    except ValueError as error:
        return fail([str(error)])
    if args.format == "markdown":
        sys.stdout.write(render_markdown(task, catalog, payload))
    else:
        json.dump(payload, sys.stdout, ensure_ascii=False, sort_keys=True)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
