"""Human-review worksheet for the saved A/B/C quiz outputs (offline only).

Run from the backend repository root:

    .\\.venv\\Scripts\\python.exe -m experiments.quiz_generation.human_review init
    .\\.venv\\Scripts\\python.exe -m experiments.quiz_generation.human_review validate
    .\\.venv\\Scripts\\python.exe -m experiments.quiz_generation.human_review summary

`init` creates results/independent_human_review_v2.json (refuses to overwrite).
`validate` is a read-only dry run; `--require-complete` also fails while any
record is unreviewed. `summary` counts only records with status REVIEWED.

The tool never calls a model or the network, never edits the saved run, dataset
or earlier review artifacts, and never fills a rating. Machine-derived
structural flags are stored apart from the human ratings and are not content
quality. See HUMAN_REVIEW_GUIDE.md for the reviewer procedure.
"""

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
RUN_PATH = RESULTS / "final_v2_run.json"
DATASET_PATH = HERE / "dataset.json"
WORKSHEET_PATH = RESULTS / "independent_human_review_v2.json"

SCHEMA = "independent-human-review-v2"
VERSIONS = {"A": "quiz-baseline-v0", "B": "quiz-gen-v1", "C": "quiz-objective-v2"}
NOT_ASSESSABLE = "NOT_ASSESSABLE"

# Criterion -> permitted values. The first value is the favourable one used only
# when summarising; no value is ever pre-filled.
RATING_SCALES = {
    "technical": ("CORRECT", "INCORRECT", NOT_ASSESSABLE),
    "relevance": ("RELEVANT", "PARTIAL", "IRRELEVANT", NOT_ASSESSABLE),
    "difficulty": ("APPROPRIATE", "TOO_EASY", "TOO_HARD", NOT_ASSESSABLE),
    "clarity": ("CLEAR", "MINOR_ISSUE", "AMBIGUOUS", NOT_ASSESSABLE),
    "uniqueness": ("EXACTLY_ONE", "MULTIPLE", "NONE", NOT_ASSESSABLE),
    "distractors": ("PLAUSIBLE_WRONG", "WEAK", "FLAWED", NOT_ASSESSABLE),
    "explanation": ("ACCURATE", "PARTIAL", "INACCURATE", NOT_ASSESSABLE),
}
# Ratings that are critical defects and need an evidence note.
CRITICAL = {
    "technical": {"INCORRECT"},
    "uniqueness": {"MULTIPLE", "NONE"},
    "explanation": {"INACCURATE"},
}
STATUSES = ("UNREVIEWED", "REVIEWED")
MIN_NOTE_LENGTH = 15
REVIEWER_ID = re.compile(r"^[A-Za-z0-9]{2,8}$")


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def question_sha256(question):
    canonical = {key: question.get(key) for key in ("text", "choices", "correct_index", "explanation")}
    payload = json.dumps(canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return sha256_bytes(payload.encode("utf-8"))


def record_id(condition, case_id, question_index):
    return f"{condition}:{case_id}:Q{question_index}"


def _blank_human_block():
    return {
        "status": "UNREVIEWED",
        "ratings": {criterion: None for criterion in RATING_SCALES},
        "evidence": None,
        "defect": None,
        "recommended_correction": None,
        "second_review": {"flag": None, "reason": None},
        "reviewer_id": None,
        "reviewed_on": None,
    }


def build_worksheet(run, dataset, run_sha256, dataset_sha256):
    cases = {case["case_id"]: case for case in dataset["cases"]}
    records = []
    for index, source in enumerate(run["records"]):
        generated = json.loads(source["raw_output"])
        case = cases[source["case_id"]]
        quality = source["quality"]
        for number, question in enumerate(generated["questions"], start=1):
            marked = question["correct_index"]
            records.append({
                "record_id": record_id(source["condition"], source["case_id"], number),
                "condition": source["condition"],
                "prompt_version": source["prompt_version"],
                "case_id": source["case_id"],
                "question_index": number,
                "source": {
                    "run_file": RUN_PATH.name,
                    "run_record_index": index,
                    "raw_output_sha256": sha256_bytes(source["raw_output"].encode("utf-8")),
                    "question_sha256": question_sha256(question),
                },
                "case_context": {
                    "difficulty_label": case["difficulty_label"],
                    "learning_objective": case["learning_objective"],
                    "rubric": case["rubric"],
                    "references": case["references"],
                },
                "question": {
                    "text": question["text"],
                    "choices": question["choices"],
                    "marked_answer_index": marked,
                    "marked_answer": question["choices"][marked],
                    "explanation": question.get("explanation"),
                },
                "machine_validation": {
                    "note": "Structural checks only; they do not establish factual correctness.",
                    "schema_valid": quality["schema_valid"],
                    "count_ok": quality["count_ok"],
                    "answers_valid": quality["answers_valid"],
                    "production_accepted": quality["production_accepted"],
                },
                "human_review": _blank_human_block(),
            })
    records.sort(key=lambda r: (r["case_id"], r["condition"], r["question_index"]))
    return {
        "schema": SCHEMA,
        "status": "PENDING_HUMAN_REVIEW",
        "guide": "HUMAN_REVIEW_GUIDE.md",
        "source_run": RUN_PATH.name,
        "dataset": dataset["dataset_version"],
        "source_sha256": {RUN_PATH.name: run_sha256, DATASET_PATH.name: dataset_sha256},
        "rating_scales": {criterion: list(values) for criterion, values in RATING_SCALES.items()},
        "critical_ratings": {criterion: sorted(values) for criterion, values in CRITICAL.items()},
        "records": records,
    }


def _load_sources():
    run_bytes = RUN_PATH.read_bytes()
    dataset_bytes = DATASET_PATH.read_bytes()
    return (
        json.loads(run_bytes.decode("utf-8")),
        json.loads(dataset_bytes.decode("utf-8")),
        sha256_bytes(run_bytes),
        sha256_bytes(dataset_bytes),
    )


def _filled(value):
    return isinstance(value, str) and bool(value.strip())


def validate_worksheet(worksheet, run, dataset, run_sha256, dataset_sha256):
    """Return (errors, stats). Pure: reads only the arguments."""
    errors = []
    stats = {"total": 0, "reviewed": 0, "in_progress": 0, "unreviewed": 0, "flagged": 0}

    if worksheet.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA!r}")
    if worksheet.get("source_sha256") != {RUN_PATH.name: run_sha256, DATASET_PATH.name: dataset_sha256}:
        errors.append("source_sha256 does not match the current saved run/dataset files")

    cases = {case["case_id"] for case in dataset["cases"]}
    expected = {}
    for index, source in enumerate(run["records"]):
        generated = json.loads(source["raw_output"])
        for number, question in enumerate(generated["questions"], start=1):
            key = record_id(source["condition"], source["case_id"], number)
            expected[key] = (index, source, question)

    seen = set()
    records = worksheet.get("records")
    if not isinstance(records, list):
        return errors + ["records must be a list"], stats

    for position, record in enumerate(records):
        rid = record.get("record_id", f"<position {position}>")
        where = f"{rid}"
        if rid in seen:
            errors.append(f"{where}: duplicate record_id")
            continue
        seen.add(rid)
        stats["total"] += 1
        if rid not in expected:
            errors.append(f"{where}: does not map to a saved output")
            continue
        index, source, question = expected[rid]
        _check_source_mapping(record, rid, index, source, question, cases, errors)
        state = _check_human_block(record.get("human_review"), question, where, errors)
        stats[state] += 1
        if state == "reviewed" and record["human_review"]["second_review"].get("flag") is True:
            stats["flagged"] += 1

    missing = sorted(set(expected) - seen)
    if missing:
        errors.append(f"missing records: {missing[:5]}{' ...' if len(missing) > 5 else ''}")
    return errors, stats


def _check_source_mapping(record, rid, index, source, question, cases, errors):
    if (record.get("condition"), record.get("case_id")) != (source["condition"], source["case_id"]):
        errors.append(f"{rid}: condition/case_id differ from the saved record")
    if record.get("prompt_version") != VERSIONS.get(source["condition"]) or \
            record.get("prompt_version") != source["prompt_version"]:
        errors.append(f"{rid}: prompt_version differs from the saved record")
    if record.get("case_id") not in cases:
        errors.append(f"{rid}: unknown case_id")
    origin = record.get("source", {})
    if origin.get("run_record_index") != index:
        errors.append(f"{rid}: source.run_record_index is wrong")
    if origin.get("raw_output_sha256") != sha256_bytes(source["raw_output"].encode("utf-8")):
        errors.append(f"{rid}: source.raw_output_sha256 does not match the saved output")
    if origin.get("question_sha256") != question_sha256(question):
        errors.append(f"{rid}: source.question_sha256 does not match the saved question")
    shown = record.get("question", {})
    marked = question["correct_index"]
    if (
        shown.get("text") != question["text"]
        or shown.get("choices") != question["choices"]
        or shown.get("marked_answer_index") != marked
        or shown.get("marked_answer") != question["choices"][marked]
        or shown.get("explanation") != question.get("explanation")
    ):
        errors.append(f"{rid}: displayed question content differs from the saved output")


def _check_human_block(block, question, where, errors):
    """Validate one human block; return 'reviewed', 'in_progress' or 'unreviewed'."""
    if not isinstance(block, dict):
        errors.append(f"{where}: human_review must be an object")
        return "unreviewed"
    status = block.get("status")
    if status not in STATUSES:
        errors.append(f"{where}: status must be one of {STATUSES}")
        return "unreviewed"
    ratings = block.get("ratings")
    if not isinstance(ratings, dict) or set(ratings) != set(RATING_SCALES):
        errors.append(f"{where}: ratings must contain exactly {sorted(RATING_SCALES)}")
        return "unreviewed"

    any_filled = False
    for criterion, value in ratings.items():
        if value is None:
            continue
        any_filled = True
        if value not in RATING_SCALES[criterion]:
            errors.append(f"{where}: invalid {criterion} rating {value!r}")
    second = block.get("second_review")
    if not isinstance(second, dict) or set(second) != {"flag", "reason"}:
        errors.append(f"{where}: second_review must have 'flag' and 'reason'")
        second = {"flag": None, "reason": None}
    other_fields = ("evidence", "defect", "recommended_correction", "reviewer_id", "reviewed_on")
    any_filled = any_filled or any(block.get(f) is not None for f in other_fields) or \
        second.get("flag") is not None or second.get("reason") is not None

    if status == "UNREVIEWED":
        return "in_progress" if any_filled else "unreviewed"

    start = len(errors)
    for criterion, value in ratings.items():
        if value is None:
            errors.append(f"{where}: REVIEWED but {criterion} is not rated")
    if not isinstance(block.get("reviewer_id"), str) or not REVIEWER_ID.match(block["reviewer_id"]):
        errors.append(f"{where}: reviewer_id must be 2-8 alphanumeric characters (initials or pseudonym)")
    try:
        date.fromisoformat(block.get("reviewed_on") or "")
    except (TypeError, ValueError):
        errors.append(f"{where}: reviewed_on must be an ISO date YYYY-MM-DD")
    if not isinstance(second.get("flag"), bool):
        errors.append(f"{where}: second_review.flag must be true or false")
    elif second["flag"] and not _filled(second.get("reason")):
        errors.append(f"{where}: second_review.reason is required when flagged")
    needs_note = any(ratings.get(c) in values for c, values in CRITICAL.items()) or \
        ratings.get("technical") == NOT_ASSESSABLE
    if needs_note and not (_filled(block.get("evidence")) and len(block["evidence"].strip()) >= MIN_NOTE_LENGTH):
        errors.append(
            f"{where}: evidence note (>= {MIN_NOTE_LENGTH} chars) required for a critical defect "
            "or NOT_ASSESSABLE technical rating"
        )
    if needs_note and not _filled(block.get("defect")):
        errors.append(f"{where}: defect description required for a critical defect")
    if question.get("explanation") in (None, "") and ratings.get("explanation") not in (None, NOT_ASSESSABLE):
        errors.append(f"{where}: no explanation exists; explanation must be NOT_ASSESSABLE")
    return "reviewed" if len(errors) == start else "in_progress"


def summarize(worksheet):
    """Distributions over REVIEWED records only; unreviewed ones are never counted."""
    reviewed = [r for r in worksheet["records"] if r["human_review"]["status"] == "REVIEWED"]
    summary = {"records": len(worksheet["records"]), "reviewed": len(reviewed), "by_condition": {}}
    for condition in VERSIONS:
        rows = [r for r in reviewed if r["condition"] == condition]
        entry = {"prompt_version": VERSIONS[condition], "reviewed": len(rows), "ratings": {}}
        for criterion in RATING_SCALES:
            entry["ratings"][criterion] = dict(sorted(
                Counter(r["human_review"]["ratings"][criterion] for r in rows).items()
            ))
        entry["flagged_for_second_review"] = sum(
            r["human_review"]["second_review"]["flag"] is True for r in rows
        )
        summary["by_condition"][condition] = entry
    return summary


def _read_worksheet(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _cmd_init(args):
    path = Path(args.path)
    if path.exists():
        print(f"Refusing to overwrite {path}", file=sys.stderr)
        return 2
    run, dataset, run_sha, dataset_sha = _load_sources()
    worksheet = build_worksheet(run, dataset, run_sha, dataset_sha)
    path.write_text(json.dumps(worksheet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Created {path} with {len(worksheet['records'])} UNREVIEWED records.")
    return 0


def _cmd_validate(args):
    run, dataset, run_sha, dataset_sha = _load_sources()
    errors, stats = validate_worksheet(_read_worksheet(args.path), run, dataset, run_sha, dataset_sha)
    for error in errors:
        print(f"ERROR: {error}")
    print(
        f"records={stats['total']} reviewed={stats['reviewed']} in_progress={stats['in_progress']} "
        f"unreviewed={stats['unreviewed']} flagged_for_second_review={stats['flagged']}"
    )
    if errors:
        return 1
    if stats["reviewed"] != stats["total"]:
        print("HUMAN REVIEW INCOMPLETE: unreviewed records are not completed reviews.")
        return 1 if args.require_complete else 0
    print("All records have a completed, valid human review.")
    return 0


def _cmd_summary(args):
    run, dataset, run_sha, dataset_sha = _load_sources()
    worksheet = _read_worksheet(args.path)
    errors, _ = validate_worksheet(worksheet, run, dataset, run_sha, dataset_sha)
    if errors:
        print(f"Worksheet has {len(errors)} validation error(s); run 'validate' first.", file=sys.stderr)
        return 1
    result = summarize(worksheet)
    result["complete"] = result["reviewed"] == result["records"]
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name, handler in (("init", _cmd_init), ("validate", _cmd_validate), ("summary", _cmd_summary)):
        command = sub.add_parser(name)
        command.add_argument("--path", default=str(WORKSHEET_PATH))
        command.set_defaults(handler=handler)
        if name == "validate":
            command.add_argument("--require-complete", action="store_true")
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
