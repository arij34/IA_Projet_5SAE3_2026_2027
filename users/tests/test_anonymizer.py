from django.test import SimpleTestCase

from users.ai.anonymizer import anonymize_fields, anonymize_text


class AnonymizerTests(SimpleTestCase):
    def test_email_is_removed(self):
        result = anonymize_text("Contact : arij.test@gmail.com pour plus d'infos")
        self.assertNotIn("@", result)
        self.assertIn("[EMAIL]", result)

    def test_phone_is_removed(self):
        result = anonymize_text("Appelez-moi au +216 20 123 456")
        self.assertNotIn("123", result)
        self.assertIn("[TELEPHONE]", result)

    def test_url_is_removed(self):
        result = anonymize_text("Mon portfolio : https://monsite.tn/projets")
        self.assertNotIn("monsite", result)
        self.assertIn("[LIEN]", result)

    def test_known_name_is_removed(self):
        result = anonymize_text("Je suis Arij Ben Salah, développeuse", known_names=["Arij", "Ben Salah"])
        self.assertNotIn("Arij", result)
        self.assertNotIn("Ben Salah", result)

    def test_known_name_is_only_removed_as_a_whole_word(self):
        self.assertEqual(anonymize_text("calcul", known_names=["Al"]), "calcul")
        self.assertEqual(anonymize_text("qualité", known_names=["Ali"]), "qualité")
        self.assertEqual(anonymize_text("Bonjour Al", known_names=["Al"]), "Bonjour [NOM]")

    def test_year_range_is_kept(self):
        result = anonymize_text("Développeur Django 2019-2023")
        self.assertIn("2019-2023", result)

    def test_empty_text(self):
        self.assertEqual(anonymize_text(None), "")
        self.assertEqual(anonymize_text(""), "")

    def test_fields_and_lists(self):
        data = {"bio": "Mail: a@b.com", "skills": ["Django", "tel 20 123 456"], "rate": 25}
        result = anonymize_fields(data)
        self.assertIn("[EMAIL]", result["bio"])
        self.assertIn("[TELEPHONE]", result["skills"][1])
        self.assertEqual(result["skills"][0], "Django")
        self.assertEqual(result["rate"], 25)
