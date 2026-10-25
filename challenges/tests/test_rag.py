import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from challenges.models import ChallengeCategory, Quiz
from challenges.services import generation, retrieval

User = get_user_model()
URL = "/api/challenges/quizzes/generate/"


def _chunk(chunk_id, categories, text, difficulty=("BEGINNER",), keywords=""):
    return {
        "id": chunk_id,
        "categories": list(categories),
        "difficulty": list(difficulty),
        "keywords": keywords,
        "source_title": f"Title {chunk_id}",
        "source_url": f"https://example.org/{chunk_id}",
        "text": text,
    }


class KnowledgeBaseTests(SimpleTestCase):
    def test_shipped_knowledge_base_is_attributed_and_covers_seeded_categories(self):
        chunks = retrieval.load_chunks()
        self.assertGreaterEqual(len(chunks), 15)
        ids = [c["id"] for c in chunks]
        self.assertEqual(len(ids), len(set(ids)))
        for chunk in chunks:
            self.assertTrue(chunk["source_url"].startswith("https://"))
            self.assertTrue(chunk["source_title"])
            self.assertLessEqual(len(chunk["text"]), retrieval.MAX_CHUNK_CHARS + 200)
        self.assertEqual(
            {slug for c in chunks for slug in c["categories"]},
            {"python", "django", "react", "typescript"},
        )

    def test_corrected_notes_keep_ids_and_state_the_qualifications(self):
        notes = {c["id"]: c["text"] for c in retrieval.load_chunks()}
        self.assertEqual(len(notes), 18)
        self.assertFalse([i for i in notes if "#" in i], "no note may be split into chunks")
        expected = {
            "py-dict-basics": ["hashable", "3.7"],
            "py-attribute-lookup": ["descriptor", "property"],
            "dj-queryset-lazy": ["same QuerySet object", "step"],
            "re-usestate-updater": ["pure", "Strict Mode"],
            "ts-typeof-truthiness": ["null", "not a primitive"],
            "dj-model-meta": ["independent"],
        }
        for note_id, phrases in expected.items():
            for phrase in phrases:
                self.assertIn(phrase, notes[note_id], note_id)
        self.assertNotIn("any immutable type", notes["py-dict-basics"])

    def test_split_text_chunks_long_documents_on_sentence_boundaries(self):
        text = " ".join(f"Sentence number {i} is here." for i in range(40))
        parts = retrieval.split_text(text, max_chars=200)
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(len(p) <= 200 for p in parts))
        self.assertEqual(" ".join(parts), text)

    def test_load_chunks_skips_invalid_documents_and_missing_file(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "kb.json"
            path.write_text(
                json.dumps({"chunks": [{"id": "x"}, _chunk("ok", ["python"], "Valid text.")]}),
                encoding="utf-8",
            )
            self.assertEqual([c["id"] for c in retrieval.load_chunks(path)], ["ok"])
            self.assertEqual(retrieval.load_chunks(Path(directory) / "missing.json"), [])
            path.write_text("not json", encoding="utf-8")
            self.assertEqual(retrieval.load_chunks(path), [])


class RetrievalTests(SimpleTestCase):
    def test_category_is_a_hard_filter(self):
        selected = retrieval.retrieve_context("django", "INTERMEDIATE", "QuerySets lazy evaluation")
        self.assertTrue(selected)
        self.assertTrue(all("django" in c["categories"] for c in selected))
        self.assertEqual(selected[0]["id"], "dj-queryset-lazy")

    def test_objective_drives_relevance_ordering(self):
        selected = retrieval.retrieve_context(
            "typescript", "ADVANCED", "discriminated unions with a literal kind property"
        )
        self.assertEqual(selected[0]["id"], "ts-discriminated-unions")

    def test_difficulty_alone_selects_matching_level_chunks(self):
        selected = retrieval.retrieve_context("python", "ADVANCED")
        self.assertTrue(selected)
        self.assertTrue(all("ADVANCED" in c["difficulty"] for c in selected))

    def test_unknown_category_and_irrelevant_chunks_return_nothing(self):
        self.assertEqual(retrieval.retrieve_context("rust", "BEGINNER", "ownership"), [])
        pool = [_chunk("a", ["python"], "Completely unrelated cooking recipe text.", ("ADVANCED",))]
        self.assertEqual(retrieval.retrieve_context("python", "BEGINNER", "list", chunks=pool), [])
        self.assertEqual(retrieval.retrieve_context("python", "BEGINNER", chunks=[]), [])

    def test_difficulty_bonus_alone_cannot_admit_chunk_when_objective_given(self):
        pool = [_chunk("a", ["python"], "Completely unrelated cooking recipe text.", ("BEGINNER",))]
        self.assertEqual(retrieval.retrieve_context("python", "BEGINNER", "list append", chunks=pool), [])
        self.assertEqual(len(retrieval.retrieve_context("python", "BEGINNER", chunks=pool)), 1)

    def test_top_k_and_character_budget_are_respected(self):
        pool = [_chunk(f"c{i}", ["python"], "x " * 100, keywords="list") for i in range(6)]
        self.assertEqual(len(retrieval.retrieve_context("python", "BEGINNER", "list", k=2, chunks=pool)), 2)
        limited = retrieval.retrieve_context("python", "BEGINNER", "list", k=6, max_chars=450, chunks=pool)
        self.assertEqual(len(limited), 2)
        self.assertEqual(retrieval.retrieve_context("python", "BEGINNER", k=0, chunks=pool), [])

    def test_retrieval_is_deterministic(self):
        args = ("react", "INTERMEDIATE", "useEffect dependencies cleanup")
        self.assertEqual(retrieval.retrieve_context(*args), retrieval.retrieve_context(*args))


class PromptConstructionTests(TestCase):
    def setUp(self):
        self.category = ChallengeCategory.objects.get(slug="python")

    @override_settings(CHALLENGE_RAG_ENABLED=False)
    def test_disabled_rag_returns_unchanged_production_prompt(self):
        system, user, version = generation.build_prompts(self.category, "BEGINNER")
        self.assertEqual(version, generation.PROMPT_VERSION)
        self.assertEqual(system, generation.SYSTEM_PROMPT)
        self.assertEqual(user, generation.build_user_prompt(self.category, "BEGINNER"))

    @override_settings(CHALLENGE_RAG_ENABLED=True)
    def test_enabled_rag_appends_sources_and_keeps_production_prompt_prefix(self):
        system, user, version = generation.build_prompts(self.category, "BEGINNER")
        base = generation.build_user_prompt(self.category, "BEGINNER")
        self.assertEqual(version, generation.RAG_PROMPT_VERSION)
        self.assertEqual(system, generation.SYSTEM_PROMPT)
        self.assertTrue(user.startswith(base))
        self.assertIn("[S1]", user)
        self.assertIn("https://docs.python.org/3/tutorial/datastructures.html", user)
        self.assertIn("n'invente aucune source", user)
        self.assertIn('"correct_index"', user)

    @override_settings(CHALLENGE_RAG_ENABLED=True)
    def test_enabled_rag_without_relevant_context_falls_back_to_v1(self):
        with patch("challenges.services.generation.retrieval.retrieve_context", return_value=[]):
            _, user, version = generation.build_prompts(self.category, "BEGINNER")
        self.assertEqual(version, generation.PROMPT_VERSION)
        self.assertEqual(user, generation.build_user_prompt(self.category, "BEGINNER"))
        self.assertNotIn("[S1]", user)


def _valid_payload():
    return {
        "title": "Python : collections",
        "questions": [
            {
                "text": f"Question {i} ?",
                "choices": [f"a{i}", f"b{i}", f"c{i}", f"d{i}"],
                "correct_index": i % 4,
                "explanation": f"Explication {i}.",
            }
            for i in range(20)
        ],
    }


def _openai_response(content):
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"choices": [{"message": {"content": content}}]}
    return response


class RagGenerationIntegrationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="rag-user",
            email="rag-user@example.com",
            password="Secret-pass-123",
            role=User.Role.FREELANCER,
            moderation_status=User.ModerationStatus.OK,
        )
        token, _ = Token.objects.get_or_create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        self.body = {"category": "python", "difficulty": "ADVANCED"}

    @override_settings(
        CHALLENGE_LLM_PROVIDER="openai", OPENAI_API_KEY="test-key", CHALLENGE_RAG_ENABLED=True
    )
    @patch("challenges.services.generation.requests.post")
    def test_rag_prompt_is_sent_recorded_and_answer_key_stays_private(self, post):
        post.return_value = _openai_response(json.dumps(_valid_payload()))
        response = self.client.post(URL, self.body, format="json")
        self.assertEqual(response.status_code, 201)
        messages = post.call_args.kwargs["json"]["messages"]
        self.assertIn("[S1]", messages[1]["content"])
        self.assertIn("docs.python.org/3/tutorial/classes.html", messages[1]["content"])
        quiz = Quiz.objects.get(pk=response.data["id"])
        self.assertEqual(quiz.prompt_version, generation.RAG_PROMPT_VERSION)
        serialized = json.dumps(response.data)
        self.assertNotIn("correct_index", serialized)
        self.assertNotIn("is_correct", serialized)
        self.assertNotIn("test-key", serialized)

    @override_settings(
        CHALLENGE_LLM_PROVIDER="openai", OPENAI_API_KEY="test-key", CHALLENGE_RAG_ENABLED=True
    )
    @patch("challenges.services.generation.requests.post")
    def test_rag_does_not_bypass_output_validation(self, post):
        payload = _valid_payload()
        payload["questions"][0]["correct_index"] = 9
        post.return_value = _openai_response(json.dumps(payload))
        response = self.client.post(URL, self.body, format="json")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(Quiz.objects.filter(source="AI_GENERATED").count(), 0)

    @override_settings(
        CHALLENGE_LLM_PROVIDER="openai", OPENAI_API_KEY="test-key", CHALLENGE_RAG_ENABLED=False
    )
    @patch("challenges.services.generation.requests.post")
    def test_disabled_rag_keeps_v1_behaviour(self, post):
        post.return_value = _openai_response(json.dumps(_valid_payload()))
        response = self.client.post(URL, self.body, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("[S1]", post.call_args.kwargs["json"]["messages"][1]["content"])
        self.assertEqual(
            Quiz.objects.get(pk=response.data["id"]).prompt_version, generation.PROMPT_VERSION
        )

    @override_settings(CHALLENGE_LLM_PROVIDER="mock", CHALLENGE_RAG_ENABLED=True)
    def test_mock_provider_records_rag_prompt_version(self):
        response = self.client.post(URL, self.body, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            Quiz.objects.get(pk=response.data["id"]).prompt_version, generation.RAG_PROMPT_VERSION
        )
