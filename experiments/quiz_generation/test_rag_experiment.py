"""Offline tests for the RAG / prompt-context optimization experiment (no network)."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from experiments.quiz_generation import rag_experiment as exp
from experiments.quiz_generation import runner

runner.setup_django()
DATASET = runner.load_dataset()
LABELS = exp.load_labels()


class RagExperimentTests(unittest.TestCase):
    def test_every_case_retrieves_relevant_context_with_objective(self):
        precisions = []
        for case in DATASET["cases"]:
            _, selected = exp.build_messages("R", case)
            metrics = exp.retrieval_metrics(case, selected, LABELS)
            # Top-ranked chunk must come from a reference page of the case.
            self.assertIn(selected[0]["source_url"], case["references"], case["case_id"])
            self.assertGreater(metrics["url_reference_coverage"], 0)
            precisions.append(metrics["url_precision"])
        self.assertGreaterEqual(sum(precisions) / len(precisions), 0.9)

    def test_labels_reference_existing_notes_and_all_cases(self):
        from challenges.services import retrieval
        kb_ids = {c["id"] for c in json.loads(
            retrieval.KNOWLEDGE_BASE_PATH.read_text(encoding="utf-8"))["chunks"]}
        self.assertEqual(set(LABELS["cases"]), {c["case_id"] for c in DATASET["cases"]})
        self.assertIn("PENDING_HUMAN_CONFIRMATION", LABELS["status"])
        for case_id, label in LABELS["cases"].items():
            self.assertTrue(label["relevant"], case_id)
            self.assertFalse(set(label["relevant"]) & set(label["borderline"]), case_id)
            self.assertLessEqual(set(label["relevant"]) | set(label["borderline"]), kb_ids, case_id)

    def test_url_match_is_not_objective_relevance(self):
        case = next(c for c in DATASET["cases"] if c["case_id"] == "DJ-INT-01")
        off_topic = [{"id": "dj-model-relationships", "text": "abc",
                      "source_url": case["references"][0]}]
        m = exp.retrieval_metrics(case, off_topic, LABELS)
        self.assertEqual(m["url_precision"], 1.0)
        self.assertEqual(m["objective_precision_strict"], 0.0)
        self.assertEqual(m["objective_not_relevant_retrieved"], ["dj-model-relationships"])

    def test_objective_metrics_strict_lenient_recall_and_split_ids(self):
        case = next(c for c in DATASET["cases"] if c["case_id"] == "PY-ADV-01")
        url = case["references"][0]
        sel = [{"id": "py-attribute-lookup#2", "text": "a", "source_url": url},
               {"id": "py-inheritance", "text": "b", "source_url": url},
               {"id": "py-list-methods", "text": "c", "source_url": url}]
        m = exp.retrieval_metrics(case, sel, LABELS)
        self.assertEqual(m["objective_precision_strict"], 0.333)
        self.assertEqual(m["objective_precision_lenient"], 0.667)
        self.assertEqual(m["objective_recall"], 0.5)

    def test_retrieval_evaluation_reports_no_objective_and_sizes_separately(self):
        ev = exp.retrieval_evaluation(DATASET, LABELS)
        self.assertEqual(set(ev["mean_over_cases"]),
                         {"with_objective_full", "with_objective_lean", "no_objective"})
        self.assertLessEqual(ev["mean_over_cases"]["with_objective_lean"]["context_chars"],
                             ev["mean_over_cases"]["with_objective_full"]["context_chars"])
        self.assertEqual(len(ev["per_case"]), 18)

    def test_baseline_prompt_is_the_unchanged_production_prompt(self):
        from experiments.quiz_generation.prompts import build_production_messages

        for case in DATASET["cases"]:
            messages, selected = exp.build_messages("B", case)
            self.assertEqual(messages, build_production_messages(case))
            self.assertEqual(selected, [])

    def test_lean_variant_is_smaller_and_limits_context(self):
        for case in DATASET["cases"]:
            full, _ = exp.build_messages("R", case)
            lean, selected = exp.build_messages("L", case)
            self.assertLess(sum(map(lambda m: len(m["content"]), lean)),
                            sum(map(lambda m: len(m["content"]), full)), case["case_id"])
            self.assertLessEqual(len(selected), exp.LEAN_TOP_K)
            self.assertLessEqual(sum(len(c["text"]) for c in selected), exp.LEAN_MAX_CHARS)
            self.assertIn("correct_index", lean[1]["content"])

    def test_empty_retrieval_falls_back_to_production_prompt(self):
        case = DATASET["cases"][0]
        with patch("challenges.services.retrieval.retrieve_context", return_value=[]):
            for condition in ("R", "L"):
                messages, selected = exp.build_messages(condition, case)
                self.assertEqual(selected, [])
                self.assertEqual(messages, exp.build_messages("B", case)[0])

    def test_retrieval_metrics_handle_irrelevant_and_empty(self):
        case = DATASET["cases"][0]
        wrong = [{"id": "x", "source_url": "https://other.example", "text": "abc"}]
        self.assertEqual(exp.retrieval_metrics(case, wrong)["url_precision"], 0.0)
        self.assertIsNone(exp.retrieval_metrics(case, [])["url_precision"])
        self.assertIsNone(exp.retrieval_metrics(case, [], LABELS)["objective_precision_strict"])

    def test_mock_run_makes_no_network_call_and_is_reproducible(self):
        with patch("requests.post", side_effect=AssertionError("network call")):
            first = exp.run(DATASET, "mock", "mock")
            second = exp.run(DATASET, "mock", "mock")
        self.assertEqual(len(first), 18)
        strip = lambda rs: [{k: v for k, v in r.items()} for r in rs]
        self.assertEqual(strip(first), strip(second))
        self.assertTrue(all(r["mode"] == "mock" and r["usage"] is None for r in first))
        report = exp.build_report(first, DATASET, "mock", "mock")
        self.assertEqual(report["real_api_calls"], 0)
        self.assertEqual(report["summary"]["B"]["source_grounded_correctness"],
                         "Not measured (manual review required)")
        self.assertEqual(report["summary"]["R"]["structural"]["tokens"], "Not measured")
        self.assertLess(report["summary"]["lean_vs_rag_estimated_input_tokens_change_pct"], 0)

    def test_real_mode_requires_explicit_flag_and_key(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch("requests.post", side_effect=AssertionError("network call")), \
                patch.object(exp, "RESULTS_DIR", Path(directory)):
            out = Path(directory) / "mock.json"
            self.assertEqual(exp.main(["--output", str(out)]), 0)
            self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["mode"], "mock")
            self.assertEqual(exp.main(["--output", str(out)]), 3)  # no overwrite
            from django.conf import settings
            with patch.object(settings, "OPENAI_API_KEY", ""):
                self.assertEqual(exp.main(["--allow-real-api", "--output", str(out) + "2"]), 2)

    def test_real_mode_refuses_more_than_the_call_cap_before_any_call(self):
        with patch("requests.post", side_effect=AssertionError("network call")):
            with self.assertRaises(ValueError):
                exp.run(DATASET, "real", "m", api_key="x", repeats=2)
            self.assertEqual(exp.MAX_REAL_CALLS, 18)

    def test_manual_review_template_is_blank(self):
        records = exp.run(DATASET, "mock", "mock")
        template = exp.manual_review_template(records)
        self.assertEqual(template["status"], "NOT_REVIEWED_BY_HUMAN")
        self.assertEqual(len(template["reviews"]), 18 * 5)
        for row in template["reviews"]:
            self.assertTrue(all(row[k] is None for k in (
                "supported_by_sources", "correct_answer_valid",
                "relevant_to_objective", "difficulty_ok", "reviewer_notes")))


if __name__ == "__main__":
    unittest.main()
