"""Offline tests for the human-review worksheet tooling (no network, no model).

    .\\.venv\\Scripts\\python.exe -m unittest experiments.quiz_generation.test_human_review -v
"""

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from experiments.quiz_generation import human_review as hr


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _complete(record, **overrides):
    block = record["human_review"]
    block["status"] = "REVIEWED"
    block["ratings"] = {
        "technical": "CORRECT", "relevance": "RELEVANT", "difficulty": "APPROPRIATE",
        "clarity": "CLEAR", "uniqueness": "EXACTLY_ONE",
        "distractors": "PLAUSIBLE_WRONG", "explanation": "ACCURATE",
    }
    block["second_review"] = {"flag": False, "reason": None}
    block["reviewer_id"] = "TST"
    block["reviewed_on"] = "2026-01-02"
    block.update(overrides)


class HumanReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved_run, cls.dataset, cls.run_sha, cls.dataset_sha = hr._load_sources()
        cls.blank = hr.build_worksheet(cls.saved_run, cls.dataset, cls.run_sha, cls.dataset_sha)

    def setUp(self):
        self.sheet = copy.deepcopy(self.blank)

    def validate(self, sheet=None):
        return hr.validate_worksheet(sheet or self.sheet, self.saved_run, self.dataset, self.run_sha, self.dataset_sha)

    def test_blank_worksheet_has_90_unique_records_and_is_valid(self):
        ids = [r["record_id"] for r in self.sheet["records"]]
        self.assertEqual(len(ids), 90)
        self.assertEqual(len(set(ids)), 90)
        errors, stats = self.validate()
        self.assertEqual(errors, [])
        self.assertEqual((stats["total"], stats["reviewed"], stats["unreviewed"]), (90, 0, 90))

    def test_every_record_maps_to_saved_output_and_nothing_is_prefilled(self):
        for record in self.sheet["records"]:
            block = record["human_review"]
            self.assertEqual(block["status"], "UNREVIEWED")
            self.assertTrue(all(v is None for v in block["ratings"].values()))
            self.assertIsNone(block["second_review"]["flag"])
        self.assertEqual({r["condition"] for r in self.sheet["records"]}, {"A", "B", "C"})

    def test_unreviewed_records_are_not_counted_as_reviews(self):
        self.assertEqual(hr.summarize(self.sheet)["reviewed"], 0)
        _complete(self.sheet["records"][0])
        summary = hr.summarize(self.sheet)
        self.assertEqual(summary["reviewed"], 1)
        condition = self.sheet["records"][0]["condition"]
        self.assertEqual(summary["by_condition"][condition]["reviewed"], 1)

    def test_partial_fill_is_in_progress_not_reviewed(self):
        self.sheet["records"][0]["human_review"]["ratings"]["technical"] = "CORRECT"
        errors, stats = self.validate()
        self.assertEqual(errors, [])
        self.assertEqual((stats["in_progress"], stats["reviewed"]), (1, 0))

    def test_completed_review_is_valid(self):
        _complete(self.sheet["records"][0])
        errors, stats = self.validate()
        self.assertEqual(errors, [])
        self.assertEqual(stats["reviewed"], 1)

    def test_reviewed_requires_every_rating(self):
        _complete(self.sheet["records"][0])
        self.sheet["records"][0]["human_review"]["ratings"]["clarity"] = None
        errors, _ = self.validate()
        self.assertTrue(any("clarity is not rated" in e for e in errors))

    def test_invalid_rating_value_is_rejected(self):
        _complete(self.sheet["records"][0])
        self.sheet["records"][0]["human_review"]["ratings"]["technical"] = "good"
        errors, _ = self.validate()
        self.assertTrue(any("invalid technical rating" in e for e in errors))

    def test_not_assessable_is_accepted_for_non_technical_criteria(self):
        _complete(self.sheet["records"][0])
        self.sheet["records"][0]["human_review"]["ratings"]["difficulty"] = hr.NOT_ASSESSABLE
        self.assertEqual(self.validate()[0], [])

    def test_critical_defect_requires_evidence_and_defect(self):
        _complete(self.sheet["records"][0])
        self.sheet["records"][0]["human_review"]["ratings"]["technical"] = "INCORRECT"
        errors, _ = self.validate()
        self.assertTrue(any("evidence note" in e for e in errors))
        self.assertTrue(any("defect description" in e for e in errors))
        self.sheet["records"][0]["human_review"].update(
            evidence="Official docs state the opposite of the marked answer.",
            defect="Marked answer contradicts the cited documentation.",
        )
        self.assertEqual(self.validate()[0], [])

    def test_technical_not_assessable_requires_note(self):
        _complete(self.sheet["records"][0])
        self.sheet["records"][0]["human_review"]["ratings"]["technical"] = hr.NOT_ASSESSABLE
        self.assertTrue(any("evidence note" in e for e in self.validate()[0]))

    def test_second_review_flag_requires_reason_and_is_counted(self):
        _complete(self.sheet["records"][0])
        self.sheet["records"][0]["human_review"]["second_review"] = {"flag": True, "reason": None}
        self.assertTrue(any("reason is required" in e for e in self.validate()[0]))
        self.sheet["records"][0]["human_review"]["second_review"] = {"flag": True, "reason": "Unsure about edge case."}
        errors, stats = self.validate()
        self.assertEqual((errors, stats["flagged"]), ([], 1))

    def test_reviewer_id_and_date_are_validated(self):
        _complete(self.sheet["records"][0])
        self.sheet["records"][0]["human_review"]["reviewer_id"] = "Jane Doe Full Name"
        self.sheet["records"][0]["human_review"]["reviewed_on"] = "17/10/2026"
        errors, _ = self.validate()
        self.assertTrue(any("reviewer_id" in e for e in errors))
        self.assertTrue(any("reviewed_on" in e for e in errors))

    def test_duplicate_unknown_and_missing_records_are_rejected(self):
        self.sheet["records"].append(copy.deepcopy(self.sheet["records"][0]))
        self.assertTrue(any("duplicate record_id" in e for e in self.validate()[0]))
        self.sheet = copy.deepcopy(self.blank)
        self.sheet["records"][0]["record_id"] = "A:UNKNOWN:Q9"
        errors, _ = self.validate()
        self.assertTrue(any("does not map" in e for e in errors))
        self.assertTrue(any("missing records" in e for e in errors))

    def test_tampered_question_or_hash_is_detected(self):
        self.sheet["records"][0]["question"]["marked_answer_index"] = 3
        self.sheet["records"][1]["source"]["question_sha256"] = "0" * 64
        errors, _ = self.validate()
        self.assertTrue(any("displayed question content" in e for e in errors))
        self.assertTrue(any("question_sha256" in e for e in errors))

    def test_source_fingerprint_mismatch_is_detected(self):
        self.sheet["source_sha256"]["final_v2_run.json"] = "0" * 64
        self.assertTrue(any("source_sha256" in e for e in self.validate()[0]))

    def test_machine_validation_is_separate_from_human_ratings(self):
        record = self.sheet["records"][0]
        self.assertIn("machine_validation", record)
        self.assertNotIn("machine_validation", record["human_review"])
        self.assertNotIn("production_accepted", record["human_review"]["ratings"])

    def test_init_refuses_to_overwrite_and_leaves_sources_untouched(self):
        before = (_sha(hr.RUN_PATH), _sha(hr.DATASET_PATH))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sheet.json"
            self.assertEqual(hr.main(["init", "--path", str(path)]), 0)
            created = path.read_bytes()
            self.assertEqual(hr.main(["init", "--path", str(path)]), 2)
            self.assertEqual(path.read_bytes(), created)
            self.assertEqual(hr.main(["validate", "--path", str(path)]), 0)
            self.assertEqual(hr.main(["validate", "--require-complete", "--path", str(path)]), 1)
            data = json.loads(created)
            self.assertEqual(len(data["records"]), 90)
        self.assertEqual(before, (_sha(hr.RUN_PATH), _sha(hr.DATASET_PATH)))


if __name__ == "__main__":
    unittest.main()
