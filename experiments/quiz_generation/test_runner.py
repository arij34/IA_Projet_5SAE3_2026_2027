"""Offline tests for the quiz-generation experiment harness (no network, no key).

    .\\.venv\\Scripts\\python.exe -m unittest experiments.quiz_generation.test_runner -v
"""

import json
import unittest
from unittest import mock

from experiments.quiz_generation import runner

runner.setup_django()

from experiments.quiz_generation.prompts import (  # noqa: E402
    BASELINE_VERSION,
    build_baseline_messages,
    build_production_messages,
)


def valid_quiz(n=5):
    return json.dumps({
        "title": "T",
        "questions": [
            {"text": f"Q{i} unique wording {i * 7}", "choices": ["a", "b", "c", "d"],
             "correct_index": i % 4, "explanation": "e"}
            for i in range(n)
        ],
    })


CASE = {"case_id": "X", "question_count": 5}


class DatasetTests(unittest.TestCase):
    def test_dataset_cases_are_complete_and_unique(self):
        dataset = runner.load_dataset()
        ids = [c["case_id"] for c in dataset["cases"]]
        self.assertEqual(len(ids), len(set(ids)))
        for case in dataset["cases"]:
            for key in ("category_name", "difficulty", "question_count",
                        "learning_objective", "references", "rubric"):
                self.assertTrue(case[key], f"{case['case_id']} missing {key}")
            self.assertTrue(all(r.startswith("https://") for r in case["references"]))


class PromptTests(unittest.TestCase):
    def setUp(self):
        self.case = runner.load_dataset()["cases"][0]

    def test_baseline_is_neutral_and_minimal(self):
        messages = build_baseline_messages(self.case)
        self.assertEqual([m["role"] for m in messages], ["user"])
        text = messages[0]["content"]
        for expected in ("Python", "Débutant", "5", "JSON"):
            self.assertIn(expected, text)

    def test_condition_b_is_the_unmodified_production_prompt(self):
        from challenges.services import generation

        messages = build_production_messages(self.case)
        self.assertEqual(messages[0]["content"], generation.SYSTEM_PROMPT)
        self.assertIn("Sujet : Python (", messages[1]["content"])
        self.assertEqual(generation.PROMPT_VERSION, "quiz-gen-v1")
        self.assertNotEqual(BASELINE_VERSION, generation.PROMPT_VERSION)


class EvaluationTests(unittest.TestCase):
    def test_valid_output_passes_all_structural_checks(self):
        q = runner.evaluate_output(valid_quiz(), CASE)
        self.assertTrue(all(q[k] for k in
                            ("schema_valid", "count_ok", "answers_valid", "production_accepted")))
        self.assertFalse(q["duplicate_flagged"])

    def test_markdown_fenced_json_is_unreadable(self):
        q = runner.evaluate_output("```json\n" + valid_quiz() + "\n```", CASE)
        self.assertFalse(q["schema_valid"])
        self.assertIn("json_unreadable", q["failure_reasons"])

    def test_wrong_count_is_schema_valid_but_not_count_ok(self):
        q = runner.evaluate_output(valid_quiz(4), CASE)
        self.assertTrue(q["schema_valid"])
        self.assertFalse(q["count_ok"])
        self.assertFalse(q["production_accepted"])

    def test_duplicate_choices_and_bad_index_fail_answer_validity(self):
        data = json.loads(valid_quiz())
        data["questions"][0]["choices"][1] = "a"
        self.assertFalse(runner.evaluate_output(json.dumps(data), CASE)["answers_valid"])
        data = json.loads(valid_quiz())
        data["questions"][1]["correct_index"] = 4
        self.assertFalse(runner.evaluate_output(json.dumps(data), CASE)["answers_valid"])
        data["questions"][1]["correct_index"] = True
        self.assertFalse(runner.evaluate_output(json.dumps(data), CASE)["answers_valid"])

    def test_near_duplicate_questions_are_flagged_for_review(self):
        data = json.loads(valid_quiz())
        data["questions"][1]["text"] = data["questions"][0]["text"]
        self.assertTrue(runner.evaluate_output(json.dumps(data), CASE)["duplicate_flagged"])


class RunnerTests(unittest.TestCase):
    def run_mock(self, repeats=1):
        dataset = runner.load_dataset()
        with mock.patch("requests.post", side_effect=AssertionError("network call")):
            records = runner.run_experiment(dataset, "mock", "mock", repeats,
                                            clock=lambda: "2000-01-01T00:00:00+00:00")
        return dataset, records

    def test_mock_run_covers_both_conditions_on_every_case_without_network(self):
        dataset, records = self.run_mock()
        self.assertEqual(len(records), len(dataset["cases"]) * 2)
        self.assertEqual({r["condition"] for r in records}, {"A", "B"})
        self.assertEqual({r["mode"] for r in records}, {"mock"})

    def test_mock_run_is_deterministic(self):
        _, first = self.run_mock()
        _, second = self.run_mock()
        self.assertEqual(first, second)

    def test_api_errors_are_separated_from_quality_failures(self):
        _, records = self.run_mock()
        errors = [r for r in records if r["api_status"] == "error"]
        self.assertEqual([(r["condition"], r["case_id"]) for r in errors], [("A", "TS-ADV-01")])
        self.assertIsNone(errors[0]["quality"])
        summary = runner.summarize(records)
        self.assertEqual(summary["A"]["api_errors"], {"numerator": 1, "denominator": 6})
        self.assertEqual(summary["A"]["schema_validity"]["denominator"], 5)

    def test_malformed_outputs_are_recorded_not_dropped(self):
        _, records = self.run_mock()
        summary = runner.summarize(records)
        self.assertEqual(summary["A"]["schema_validity"], {"numerator": 4, "denominator": 5})
        self.assertEqual(summary["A"]["question_count_compliance"],
                         {"numerator": 3, "denominator": 5})
        self.assertEqual(summary["B"]["schema_validity"], {"numerator": 6, "denominator": 6})
        self.assertEqual(summary["B"]["answer_validity"], {"numerator": 4, "denominator": 6})

    def test_unmeasured_metrics_are_never_fabricated(self):
        _, records = self.run_mock()
        entry = runner.summarize(records)["B"]
        self.assertEqual(entry["latency_seconds"]["mean"], "Not measured")
        self.assertEqual(entry["tokens"], "Not measured")
        self.assertEqual(entry["estimated_cost_usd"], "Not measured")
        self.assertIn("Not measured", entry["factual_accuracy"])

    def test_cost_requires_usage_and_explicit_prices(self):
        records = [{
            "condition": "A", "prompt_version": "v", "api_status": "ok", "latency_seconds": 1.5,
            "usage": {"prompt_tokens": 1000, "completion_tokens": 500},
            "quality": runner.evaluate_output(valid_quiz(), CASE),
        }]
        self.assertEqual(runner.summarize(records)["A"]["estimated_cost_usd"], "Not measured")
        priced = runner.summarize(records, {"input_per_1m": 1.0, "output_per_1m": 2.0})
        self.assertEqual(priced["A"]["estimated_cost_usd"], 0.002)
        self.assertEqual(priced["A"]["latency_seconds"]["mean"], 1.5)

    def test_report_labels_mock_results_as_harness_validation(self):
        dataset, records = self.run_mock()
        report = runner.build_report(records, dataset, "mock", "mock")
        self.assertEqual(report["real_api_calls"], 0)
        self.assertIn("harness validation only", report["interpretation"])


class ObjectiveConditionTests(unittest.TestCase):
    def setUp(self):
        self.cases = runner.load_dataset()["cases"]

    def test_candidate_includes_objective_and_rubric_for_every_case(self):
        from experiments.quiz_generation.prompts import build_objective_messages

        for case in self.cases:
            messages = build_objective_messages(case)
            self.assertEqual([m["role"] for m in messages], ["system", "user"])
            self.assertIn(case["learning_objective"], messages[1]["content"])
            self.assertIn(case["rubric"], messages[1]["content"])
            self.assertIn("contraignants", messages[0]["content"])
            self.assertIn("ne prétends jamais", messages[0]["content"])

    def test_candidate_extends_production_prompt_without_altering_it(self):
        from challenges.services import generation
        from experiments.quiz_generation.prompts import (
            OBJECTIVE_VERSION,
            build_objective_messages,
        )

        case = self.cases[0]
        base = build_production_messages(case)
        baseline = build_baseline_messages(case)
        cand = build_objective_messages(case)
        self.assertEqual(OBJECTIVE_VERSION, "quiz-objective-v2")
        self.assertTrue(cand[0]["content"].startswith(generation.SYSTEM_PROMPT))
        self.assertTrue(cand[1]["content"].startswith(base[1]["content"]))
        self.assertEqual(build_baseline_messages(case), baseline)
        self.assertEqual(build_production_messages(case), base)

    def test_candidate_contains_correctness_and_domain_guardrails(self):
        from experiments.quiz_generation.prompts import build_objective_messages

        for case in self.cases:
            text = "\n".join(m["content"] for m in build_objective_messages(case)).casefold()
            for concept in (
                "sans ambiguïté",
                "exactement une réponse défendable",
                "distracteurs",
                "correct_index",
                "si le sujet concerne django",
                "si le sujet concerne typescript",
                "typeof",
                "à la compilation",
            ):
                self.assertIn(concept, text)
        text = "\n".join(
            m["content"] for m in build_objective_messages(
                next(c for c in self.cases if c["category_name"] == "Django")
            )
        )
        self.assertIn(".save()", text)
        self.assertIn(".objects.create()", text)
        ts_text = "\n".join(
            m["content"] for m in build_objective_messages(
                next(c for c in self.cases if c["category_name"] == "TypeScript")
            )
        )
        self.assertIn("objets variants partageant un discriminant", ts_text)
        self.assertIn("exécution", ts_text)

    def test_candidate_does_not_claim_references_were_consulted(self):
        from experiments.quiz_generation.prompts import build_objective_messages

        case = self.cases[0]
        user = build_objective_messages(case)[1]["content"]
        self.assertNotIn(case["references"][0], user)
        self.assertIn("sans prétendre avoir consulté", user)

    def test_existing_conditions_never_receive_objective_or_rubric(self):
        for case in self.cases:
            for messages in (build_baseline_messages(case), build_production_messages(case)):
                text = " ".join(m["content"] for m in messages)
                self.assertNotIn(case["learning_objective"], text)
                self.assertNotIn(case["rubric"], text)

    def test_default_conditions_and_versions_are_unchanged(self):
        from experiments.quiz_generation.prompts import CONDITIONS

        self.assertEqual(runner.DEFAULT_CONDITIONS, ("A", "B"))
        self.assertEqual(CONDITIONS["A"][0], "quiz-baseline-v0")
        self.assertEqual(CONDITIONS["B"][0], "quiz-gen-v1")
        self.assertEqual(CONDITIONS["C"][0], "quiz-objective-v2")

    def test_mock_run_with_candidate_makes_no_network_call(self):
        dataset = runner.load_dataset()
        with mock.patch("requests.post", side_effect=AssertionError("network call")):
            records = runner.run_experiment(dataset, "mock", "mock", 1,
                                            conditions=("A", "C"))
        self.assertEqual(len(records), len(dataset["cases"]) * 2)
        self.assertEqual({r["prompt_version"] for r in records},
                         {"quiz-baseline-v0", "quiz-objective-v2"})
        self.assertEqual({r["mode"] for r in records}, {"mock"})

    def test_invalid_condition_is_rejected(self):
        with self.assertRaises(SystemExit):
            runner.main(["--conditions", "A,Z"])

    def test_real_run_refuses_to_overwrite_existing_results(self):
        import tempfile
        from pathlib import Path

        from django.test import override_settings

        with tempfile.TemporaryDirectory() as tmp:
            existing = Path(tmp) / "existing.json"
            existing.write_text("keep", encoding="utf-8")
            with mock.patch("requests.post", side_effect=AssertionError("network call")), \
                    override_settings(OPENAI_API_KEY="dummy-not-a-real-key"):
                code = runner.main(["--allow-real-api", "--conditions", "C",
                                    "--output", str(existing)])
            self.assertEqual(code, 3)
            self.assertEqual(existing.read_text(encoding="utf-8"), "keep")


class RealModeGuardTests(unittest.TestCase):
    def test_real_mode_refused_without_flag_default_is_mock(self):
        with mock.patch("requests.post", side_effect=AssertionError("network call")), \
                mock.patch.object(runner, "RESULTS_DIR", runner.RESULTS_DIR), \
                mock.patch("pathlib.Path.write_text"):
            self.assertEqual(runner.main([]), 0)

    def test_real_mode_refused_without_backend_key(self):
        with mock.patch("requests.post", side_effect=AssertionError("network call")), \
                self.settings_without_key():
            self.assertEqual(runner.main(["--allow-real-api"]), 2)

    def settings_without_key(self):
        from django.test import override_settings

        return override_settings(OPENAI_API_KEY="")


if __name__ == "__main__":
    unittest.main()
