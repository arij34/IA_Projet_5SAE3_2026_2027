"""Controlled prompt experiment: baseline (A) vs production quiz-gen-v1 (B).

Standalone script, not part of the Django suite (same convention as
experiments/compare_models.py). Run from the backend repo root:

    .\\.venv\\Scripts\\python.exe -m experiments.quiz_generation.runner            # mock, offline
    .\\.venv\\Scripts\\python.exe -m experiments.quiz_generation.runner --allow-real-api --repeats 1

Default mode is MOCK: deterministic synthetic responses, zero network calls.
Mock results only validate the harness; they say nothing about real-model quality.
Real mode needs --allow-real-api AND OPENAI_API_KEY in the backend environment
(.env). The key is never printed or written to results.
"""

import argparse
import json
import os
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATASET_PATH = HERE / "dataset.json"
RESULTS_DIR = HERE / "results"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
TEMPERATURE = 0.4
CHOICES = 4
DUPLICATE_JACCARD = 0.8
DEFAULT_CONDITIONS = ("A", "B")


def setup_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import django

    django.setup()


def load_dataset(path: Path = DATASET_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- evaluation


def _tokens(text: str) -> set:
    return set(re.findall(r"\w+", text.casefold()))


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    return len(ta & tb) / len(ta | tb) if ta | tb else 0.0


def evaluate_output(raw, case: dict) -> dict:
    """Automatic structural checks on one raw model output (quality, not API)."""
    result = {
        "schema_valid": False,
        "count_ok": False,
        "answers_valid": False,
        "production_accepted": False,
        "duplicate_flagged": None,
        "failure_reasons": [],
    }
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        result["failure_reasons"].append("json_unreadable")
        return result
    questions = data.get("questions") if isinstance(data, dict) else None
    if not isinstance(questions, list) or not isinstance(data.get("title"), str):
        result["failure_reasons"].append("structure")
        return result
    items_ok = all(
        isinstance(q, dict)
        and isinstance(q.get("text"), str)
        and isinstance(q.get("choices"), list)
        and isinstance(q.get("explanation"), str)
        and "correct_index" in q
        for q in questions
    )
    if not items_ok:
        result["failure_reasons"].append("question_fields")
        return result
    result["schema_valid"] = True
    result["count_ok"] = len(questions) == case["question_count"]
    if not result["count_ok"]:
        result["failure_reasons"].append("question_count")

    def answer_ok(q):
        choices = q["choices"]
        idx = q["correct_index"]
        return (
            len(choices) == CHOICES
            and all(isinstance(c, str) and c.strip() for c in choices)
            and len({c.strip().casefold() for c in choices}) == CHOICES
            and isinstance(idx, int)
            and not isinstance(idx, bool)
            and 0 <= idx < CHOICES
        )

    result["answers_valid"] = bool(questions) and all(answer_ok(q) for q in questions)
    if not result["answers_valid"]:
        result["failure_reasons"].append("answers")

    texts = [q["text"] for q in questions]
    result["duplicate_flagged"] = any(
        _jaccard(texts[i], texts[j]) >= DUPLICATE_JACCARD
        for i in range(len(texts))
        for j in range(i + 1, len(texts))
    )

    from challenges.services.generation import QuizGenerationError, parse_generated_quiz

    try:
        parse_generated_quiz(raw)
        result["production_accepted"] = True
    except QuizGenerationError as exc:
        result["failure_reasons"].append(f"production_parser: {exc}")
    return result


def _rate(records, key):
    return {
        "numerator": sum(1 for r in records if r["quality"][key]),
        "denominator": len(records),
    }


def summarize(records: list[dict], prices: dict | None = None) -> dict:
    """Per-condition summary. Quality denominators exclude API errors, reported apart."""
    summary = {}
    for condition in sorted({r["condition"] for r in records}):
        subset = [r for r in records if r["condition"] == condition]
        completed = [r for r in subset if r["api_status"] == "ok"]
        schema_ok = [r for r in completed if r["quality"]["schema_valid"]]
        latencies = [r["latency_seconds"] for r in completed if r["latency_seconds"] is not None]
        with_usage = [r for r in completed if r["usage"]]
        entry = {
            "prompt_version": subset[0]["prompt_version"],
            "calls_attempted": len(subset),
            "api_errors": {
                "numerator": len(subset) - len(completed),
                "denominator": len(subset),
            },
            "schema_validity": _rate(completed, "schema_valid"),
            "question_count_compliance": _rate(completed, "count_ok"),
            "answer_validity": _rate(completed, "answers_valid"),
            "production_parser_acceptance": _rate(completed, "production_accepted"),
            "duplicate_flagged_heuristic": {
                "numerator": sum(1 for r in schema_ok if r["quality"]["duplicate_flagged"]),
                "denominator": len(schema_ok),
            },
            "latency_seconds": {
                "mean": round(statistics.mean(latencies), 3) if latencies else "Not measured",
                "n": len(latencies),
            },
            "tokens": "Not measured",
            "estimated_cost_usd": "Not measured",
            "factual_accuracy": "Not measured (manual review required)",
            "relevance_difficulty": "Not measured (manual review required)",
        }
        if with_usage:
            prompt = sum(r["usage"].get("prompt_tokens", 0) for r in with_usage)
            completion = sum(r["usage"].get("completion_tokens", 0) for r in with_usage)
            entry["tokens"] = {"prompt": prompt, "completion": completion, "n": len(with_usage)}
            if prices:
                entry["estimated_cost_usd"] = round(
                    prompt / 1e6 * prices["input_per_1m"]
                    + completion / 1e6 * prices["output_per_1m"],
                    6,
                )
        summary[condition] = entry
    return summary


# ------------------------------------------------------------------ providers


def _quiz(case, n=5, **override):
    questions = [
        {
            "text": f"Question synthétique {i + 1} sur {case['category_name']} ?",
            "choices": [f"Choix {c} {i + 1}" for c in "ABCD"],
            "correct_index": i % CHOICES,
            "explanation": "Explication synthétique.",
        }
        for i in range(n)
    ]
    return {"title": f"{case['category_name']} (synthétique)", "questions": questions, **override}


# Deterministic synthetic failure scenarios, keyed by (condition, case_id).
# Anything not listed returns a structurally valid synthetic quiz.
MOCK_SCENARIOS = {
    ("A", "PY-ADV-01"): "fenced_json",
    ("A", "DJ-INT-01"): "four_questions",
    ("A", "TS-ADV-01"): "api_error",
    ("B", "RE-INT-01"): "duplicate_choices",
    ("B", "DJ-BEG-01"): "bad_correct_index",
}


def mock_call(condition: str, case: dict, messages: list[dict]) -> dict:
    """Deterministic offline provider. Never returns latency or token usage."""
    scenario = MOCK_SCENARIOS.get((condition, case["case_id"]), "valid")
    if scenario == "api_error":
        return {"api_status": "error", "error": "mock HTTP 503", "raw": None,
                "latency_seconds": None, "usage": None, "scenario": scenario}
    if scenario == "fenced_json":
        raw = "```json\n" + json.dumps(_quiz(case)) + "\n```"
    elif scenario == "four_questions":
        raw = json.dumps(_quiz(case, n=4))
    elif scenario == "duplicate_choices":
        quiz = _quiz(case)
        quiz["questions"][0]["choices"][1] = quiz["questions"][0]["choices"][0]
        raw = json.dumps(quiz)
    elif scenario == "bad_correct_index":
        quiz = _quiz(case)
        quiz["questions"][2]["correct_index"] = 4
        raw = json.dumps(quiz)
    else:
        raw = json.dumps(_quiz(case))
    return {"api_status": "ok", "error": None, "raw": raw,
            "latency_seconds": None, "usage": None, "scenario": scenario}


def real_call(condition: str, case: dict, messages: list[dict], model: str, api_key: str,
              timeout: float) -> dict:
    """Real OpenAI call. Only reachable via --allow-real-api. Key is never recorded."""
    import requests

    started = time.perf_counter()
    try:
        response = requests.post(
            OPENAI_URL,
            headers={"Authorization": "Bearer " + api_key},
            json={
                "model": model,
                "temperature": TEMPERATURE,
                "response_format": {"type": "json_object"},
                "messages": messages,
            },
            timeout=timeout,
        )
    except requests.RequestException as exc:
        return {"api_status": "error", "error": type(exc).__name__, "raw": None,
                "latency_seconds": None, "usage": None, "scenario": "real"}
    latency = round(time.perf_counter() - started, 3)
    if response.status_code >= 400:
        return {"api_status": "error", "error": f"HTTP {response.status_code}", "raw": None,
                "latency_seconds": latency, "usage": None, "scenario": "real"}
    try:
        body = response.json()
        raw = body["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError):
        return {"api_status": "error", "error": "unusable_response_body", "raw": None,
                "latency_seconds": latency, "usage": None, "scenario": "real"}
    return {"api_status": "ok", "error": None, "raw": raw, "latency_seconds": latency,
            "usage": body.get("usage"), "scenario": "real"}


# --------------------------------------------------------------------- driver


def run_experiment(dataset: dict, mode: str, model: str, repeats: int = 1,
                   api_key: str | None = None, timeout: float = 45,
                   clock=lambda: datetime.now(timezone.utc).isoformat(),
                   conditions: tuple = DEFAULT_CONDITIONS) -> list[dict]:
    from experiments.quiz_generation.prompts import CONDITIONS

    records = []
    for case in dataset["cases"]:
        for condition in conditions:
            version, build = CONDITIONS[condition]
            messages = build(case)
            for repeat in range(1, repeats + 1):
                if mode == "real":
                    call = real_call(condition, case, messages, model, api_key, timeout)
                else:
                    call = mock_call(condition, case, messages)
                quality = (
                    evaluate_output(call["raw"], case)
                    if call["api_status"] == "ok"
                    else None
                )
                records.append({
                    "timestamp": clock(),
                    "mode": mode,
                    "case_id": case["case_id"],
                    "condition": condition,
                    "prompt_version": version,
                    "repeat": repeat,
                    "model": model if mode == "real" else "mock",
                    "settings": {"temperature": TEMPERATURE,
                                 "response_format": "json_object"},
                    "api_status": call["api_status"],
                    "error": call["error"],
                    "scenario": call["scenario"],
                    "latency_seconds": call["latency_seconds"],
                    "usage": call["usage"],
                    "raw_output": call["raw"],
                    "quality": quality,
                })
    return records


def build_report(records, dataset, mode, model, prices=None) -> dict:
    return {
        "mode": mode,
        "real_api_calls": sum(1 for r in records if r["mode"] == "real"),
        "interpretation": (
            "MOCK / harness validation only: synthetic outputs, no real-model quality evidence."
            if mode == "mock"
            else "Real-model run; factual accuracy still requires manual review."
        ),
        "model": model if mode == "real" else "mock",
        "dataset_version": dataset["dataset_version"],
        "case_count": len(dataset["cases"]),
        "pricing": prices or "Not provided: cost not computed",
        "summary": summarize(records, prices),
        "records": records,
    }


def manual_review_template(dataset: dict) -> dict:
    return {
        "instructions": (
            "For each generated question, compare to the case references/rubric. "
            "Set factual_accuracy to correct/incorrect/unverifiable, ambiguous to true/false, "
            "relevant and difficulty_ok to true/false. null means Not measured."
        ),
        "cases": [
            {"case_id": c["case_id"], "references": c["references"], "rubric": c["rubric"]}
            for c in dataset["cases"]
        ],
        "review_fields": ["case_id", "condition", "question_index", "factual_accuracy",
                          "ambiguous", "relevant", "difficulty_ok", "reviewer_notes"],
        "reviews": [],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--allow-real-api", action="store_true",
                        help="Explicitly authorize real OpenAI calls (default: mock).")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--price-input-per-1m", type=float)
    parser.add_argument("--price-output-per-1m", type=float)
    parser.add_argument("--conditions", default=",".join(DEFAULT_CONDITIONS),
                        help="Comma-separated prompt conditions among A,B,C (default: A,B).")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--overwrite", action="store_true",
                        help="Allow replacing an existing real-run results file.")
    args = parser.parse_args(argv)
    conditions = tuple(c.strip().upper() for c in args.conditions.split(",") if c.strip())
    if not conditions or any(c not in ("A", "B", "C") for c in conditions):
        parser.error("--conditions must be a comma-separated subset of A,B,C")

    setup_django()
    from django.conf import settings

    dataset = load_dataset()
    mode = "real" if args.allow_real_api else "mock"
    api_key = None
    if mode == "real":
        api_key = getattr(settings, "OPENAI_API_KEY", "")
        if not api_key:
            print("Refusing real run: OPENAI_API_KEY is not configured in the backend environment.")
            return 2
    prices = None
    if args.price_input_per_1m is not None and args.price_output_per_1m is not None:
        prices = {"input_per_1m": args.price_input_per_1m,
                  "output_per_1m": args.price_output_per_1m}
    model = settings.OPENAI_MODEL
    if "C" in conditions:
        default_name = "objective_mock_run.json" if mode == "mock" else "objective_run.json"
    else:
        default_name = f"{mode}_run.json"
    output = args.output or RESULTS_DIR / default_name
    if mode == "real" and output.exists() and not args.overwrite:
        print(f"Refusing to overwrite existing results file: {output} (use --output or --overwrite).")
        return 3
    records = run_experiment(dataset, mode, model, args.repeats, api_key,
                             settings.OPENAI_TIMEOUT_SECONDS, conditions=conditions)
    report = build_report(records, dataset, mode, model, prices)
    RESULTS_DIR.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    template = RESULTS_DIR / "manual_review_template.json"
    if not template.exists():
        template.write_text(json.dumps(manual_review_template(dataset),
                                       ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"mode={mode} real_api_calls={report['real_api_calls']} -> {output}")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
