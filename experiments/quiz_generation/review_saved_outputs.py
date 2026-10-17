"""Validate and summarize the offline, question-level review of final_v2_run.json.

Run from the backend repository root:

    .\\.venv\\Scripts\\python.exe -m experiments.quiz_generation.review_saved_outputs

Add ``--write-independent-template`` to create a blank, question-level human
review worksheet. That option refuses to overwrite an existing worksheet.

This utility makes no network calls and does not modify either input artifact.
It validates review coverage and summarizes the recorded reviewer judgments;
it does not decide whether generated content is technically correct.

The TSV uses these ratings:

* technical: correct marked answer, incorrect marked answer/no valid option, or
  unverified against the supplied evidence;
* relevance: aligned to the case objective, partly aligned, or off-topic;
* difficulty: aligned, too easy, too hard, or uncertain (a subjective judgment);
* clarity: clear, minor issue, ambiguous, or unclear;
* uniqueness: exactly one defensible answer, multiple, none, or uncertain;
* distractors: plausible and wrong, weak, competing, or uncertain;
* explanation: accurate, partial, incorrect, or unavailable.

Severity is per question: high for a clearly wrong key, no valid answer, or
invalid code that changes the answer; medium for material ambiguity or objective
mismatch; low for a limited clarity, difficulty, or distractor weakness; none
where no material defect was recorded. Findings are first-pass judgments and
require independent human review.
"""

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
RUN_PATH = RESULTS / "final_v2_run.json"
DATASET_PATH = HERE / "dataset.json"
REVIEWS_PATH = RESULTS / "offline_quality_review_v1.tsv"
HUMAN_TEMPLATE_PATH = RESULTS / "independent_human_review_template_v1.json"

VERSIONS = {
    "A": "quiz-baseline-v0",
    "B": "quiz-gen-v1",
    "C": "quiz-objective-v2",
}
RATING_FIELDS = {
    "technical": {"correct", "incorrect", "unverified"},
    "relevance": {"aligned", "partial", "off_topic"},
    "difficulty": {"aligned", "too_easy", "too_hard", "uncertain"},
    "clarity": {"clear", "minor", "ambiguous", "unclear"},
    "uniqueness": {"one", "multiple", "none", "uncertain"},
    "distractors": {"plausible", "weak", "competing", "uncertain"},
    "explanation": {"accurate", "partial", "incorrect", "unavailable"},
    "severity": {"none", "low", "medium", "high"},
}
SUCCESS_RATINGS = {
    "technical": "correct",
    "relevance": "aligned",
    "difficulty": "aligned",
    "clarity": "clear",
    "uniqueness": "one",
    "distractors": "plausible",
    "explanation": "accurate",
}


def _load_reviews():
    with REVIEWS_PATH.open(encoding="utf-8", newline="") as stream:
        lines = (line for line in stream if not line.startswith("#"))
        return list(csv.DictReader(lines, delimiter="|"))


def _fraction(count, total):
    return {
        "count": count,
        "denominator": total,
        "proportion": round(count / total, 4) if total else None,
    }


def build_human_template(run, dataset):
    cases = {case["case_id"]: case for case in dataset["cases"]}
    questions = []
    for record in run["records"]:
        generated = json.loads(record["raw_output"])
        case = cases[record["case_id"]]
        for question_index, question in enumerate(generated["questions"], start=1):
            marked_index = question["correct_index"]
            questions.append({
                "condition": record["condition"],
                "prompt_version": record["prompt_version"],
                "case_id": record["case_id"],
                "question_index": question_index,
                "learning_objective": case["learning_objective"],
                "rubric": case["rubric"],
                "references": case["references"],
                "text": question["text"],
                "choices": question["choices"],
                "marked_answer_index": marked_index,
                "marked_answer": question["choices"][marked_index],
                "explanation": question.get("explanation"),
                "human_status": "NOT_REVIEWED_BY_HUMAN",
                "ratings": {field: None for field in SUCCESS_RATINGS},
                "technical": None,
                "evidence": None,
                "defect": None,
                "severity": None,
                "recommended_correction": None,
                "reviewer": None,
                "reviewed_at": None,
            })
    return {
        "template": "independent-human-review-v1",
        "status": "PENDING_HUMAN_REVIEW",
        "source_run": RUN_PATH.name,
        "dataset": dataset["dataset_version"],
        "ratings_are_blank": True,
        "questions": questions,
    }


def build_report():
    run = json.loads(RUN_PATH.read_text(encoding="utf-8"))
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    cases = {case["case_id"]: case for case in dataset["cases"]}
    if run.get("mode") != "real" or run.get("real_api_calls") != 18:
        raise ValueError("Expected the saved 18-call real-model artifact.")
    if set(cases) != {record["case_id"] for record in run["records"]}:
        raise ValueError("Saved run cases do not match the dataset.")

    records = {}
    structural_counts = {
        "schema_valid": Counter(),
        "count_ok": Counter(),
        "answers_valid": Counter(),
        "production_accepted": Counter(),
        "api_errors": Counter(),
    }
    for record in run["records"]:
        condition = record["condition"]
        case_id = record["case_id"]
        key = (condition, case_id)
        if condition not in VERSIONS or key in records:
            raise ValueError(f"Unexpected or duplicate output record: {key}")
        if record["prompt_version"] != VERSIONS[condition]:
            raise ValueError(f"Prompt version mismatch for {key}.")
        if record["repeat"] != 1 or record["api_status"] != "ok":
            raise ValueError(f"Unexpected repeat or API status for {key}.")
        output = json.loads(record["raw_output"])
        expected = cases[case_id]["question_count"]
        if len(output.get("questions", [])) != expected:
            raise ValueError(f"Question count changed for {key}.")
        records[key] = (record, output)
        for field in ("schema_valid", "count_ok", "answers_valid", "production_accepted"):
            structural_counts[field][condition] += bool(record["quality"][field])
        structural_counts["api_errors"][condition] += record["api_status"] != "ok"

    expected_records = {(condition, case_id) for condition in VERSIONS for case_id in cases}
    if set(records) != expected_records:
        raise ValueError("The run must contain exactly one output per condition and case.")
    models = {record["model"] for record, _ in records.values()}
    settings = {
        json.dumps(record["settings"], sort_keys=True)
        for record, _ in records.values()
    }
    if models != {run["model"]} or len(settings) != 1:
        raise ValueError("Saved model/settings metadata is inconsistent.")

    reviews = _load_reviews()
    review_index = {}
    for review in reviews:
        key = (review["condition"], review["case_id"])
        try:
            question_index = int(review["question"])
        except ValueError as exc:
            raise ValueError(f"Invalid question number for {key}.") from exc
        full_key = (*key, question_index)
        if full_key in review_index:
            raise ValueError(f"Duplicate review row: {full_key}")
        if key not in records or not 1 <= question_index <= len(records[key][1]["questions"]):
            raise ValueError(f"Review row does not identify a saved question: {full_key}")
        if not review["evidence"] or not review["defect"] or not review["correction"]:
            raise ValueError(f"Incomplete evidence or action fields for {full_key}.")
        for field, allowed in RATING_FIELDS.items():
            if review[field] not in allowed:
                raise ValueError(f"Invalid {field} rating for {full_key}: {review[field]}")
        review_index[full_key] = review

    expected_reviews = {
        (condition, case_id, question_index)
        for condition, case_id in expected_records
        for question_index in range(1, len(records[(condition, case_id)][1]["questions"]) + 1)
    }
    if set(review_index) != expected_reviews:
        missing = sorted(expected_reviews - set(review_index))
        extra = sorted(set(review_index) - expected_reviews)
        raise ValueError(f"Review coverage mismatch; missing={missing}, extra={extra}")

    by_condition = {}
    for condition in VERSIONS:
        selected = [row for key, row in review_index.items() if key[0] == condition]
        total = len(selected)
        ratings = {}
        for field in SUCCESS_RATINGS:
            good = sum(row[field] == SUCCESS_RATINGS[field] for row in selected)
            ratings[field] = {
                "positive": _fraction(good, total),
                "distribution": dict(sorted(Counter(row[field] for row in selected).items())),
            }
        severity = Counter(row["severity"] for row in selected)
        by_condition[condition] = {
            "prompt_version": VERSIONS[condition],
            "questions_reviewed": total,
            "ratings": ratings,
            "severity_questions": dict(sorted(severity.items())),
            "questions_with_findings": sum(row["severity"] != "none" for row in selected),
        }

    structure = {}
    for condition in VERSIONS:
        structure[condition] = {
            "prompt_version": VERSIONS[condition],
            "outputs": len(cases),
            "api_errors": structural_counts["api_errors"][condition],
            "structural_checks": {
                field: _fraction(structural_counts[field][condition], len(cases))
                for field in ("schema_valid", "count_ok", "answers_valid", "production_accepted")
            },
            "latency_mean_seconds": run["summary"][condition]["latency_seconds"]["mean"],
            "tokens": {
                "prompt": run["summary"][condition]["tokens"]["prompt"],
                "completion": run["summary"][condition]["tokens"]["completion"],
                "total": (
                    run["summary"][condition]["tokens"]["prompt"]
                    + run["summary"][condition]["tokens"]["completion"]
                ),
            },
            "cost": "Not measured",
        }

    return {
        "evaluation": "offline-quality-review-v1",
        "source_run": RUN_PATH.name,
        "dataset": dataset["dataset_version"],
        "model": run["model"],
        "generation_settings": json.loads(next(iter(settings))),
        "source_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (RUN_PATH, DATASET_PATH, REVIEWS_PATH)
        },
        "method": (
            "AI-assisted first-pass judgments recorded in the TSV; the script "
            "validates identity/coverage and summarizes ratings only; it does "
            "not reproduce the saved model generation."
        ),
        "network_calls": 0,
        "regenerated_outputs": 0,
        "structural": structure,
        "content_review": by_condition,
        "review_limitations": [
            "One AI-assisted reviewer; no independent human or subject-matter adjudication.",
            "Difficulty, clarity, and distractor quality are judgment-based.",
            "Only disputed/high-impact technical details received focused runtime or official-reference checks.",
            "One model run and one output per case-condition; descriptive counts are not significance tests.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--write-independent-template",
        action="store_true",
        help="Create the blank human-review worksheet; refuses to overwrite it.",
    )
    args = parser.parse_args()
    report = build_report()
    if args.write_independent_template:
        if HUMAN_TEMPLATE_PATH.exists():
            raise FileExistsError(f"Refusing to overwrite {HUMAN_TEMPLATE_PATH}")
        run = json.loads(RUN_PATH.read_text(encoding="utf-8"))
        dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
        template = build_human_template(run, dataset)
        if len(template["questions"]) != 90:
            raise ValueError("Expected 90 questions in the human-review template.")
        HUMAN_TEMPLATE_PATH.write_text(
            json.dumps(template, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        report["independent_human_template"] = HUMAN_TEMPLATE_PATH.name
        report["human_template_status"] = template["status"]
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
