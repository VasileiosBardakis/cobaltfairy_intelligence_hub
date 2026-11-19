import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import theme_labeling as labeling


class TestThemeLabeling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.themes = labeling.load_taxonomy()

    def test_taxonomy_override(self):
        peak = self.themes[self.themes["theme_id"] == "peak_season_bfcm"].iloc[0]
        self.assertIn("email marketing competitors", peak["description"])
        self.assertEqual(len(self.themes), 8)

    def test_valid_labels(self):
        post = "We use generative AI to create emails for Black Friday."
        output = {
            "labels": [
                {"theme_id": "ai_automation", "confidence": 0.9,
                 "evidence_quote": "generative AI"},
                {"theme_id": "peak_season_bfcm", "confidence": 0.8,
                 "evidence_quote": "Black Friday"},
            ],
            "new_themes": [],
        }
        labels, new_themes, warnings = labeling.validate_output(output, post, self.themes)
        self.assertEqual(len(labels), 2)
        self.assertEqual(new_themes, [])
        self.assertEqual(warnings, [])

    def test_duplicate_theme_keeps_highest_confidence(self):
        post = "We use generative AI."
        output = {
            "labels": [
                {"theme_id": "ai_automation", "confidence": 0.6,
                 "evidence_quote": "generative AI"},
                {"theme_id": "ai_automation", "confidence": 0.9,
                 "evidence_quote": "generative AI"},
            ],
            "new_themes": [],
        }
        labels, _, warnings = labeling.validate_output(output, post, self.themes)
        self.assertEqual(len(labels), 1)
        self.assertEqual(labels[0]["confidence"], 0.9)
        self.assertEqual(warnings, [])

    def test_bad_quote_is_dropped(self):
        post = "We use generative AI."
        output = {
            "labels": [{"theme_id": "ai_automation", "confidence": 0.9,
                        "evidence_quote": "invented quote"}],
            "new_themes": [],
        }
        labels, _, warnings = labeling.validate_output(output, post, self.themes)
        self.assertEqual(labels, [])
        self.assertTrue(warnings)

    def test_unknown_theme_is_dropped(self):
        post = "We use generative AI."
        output = {
            "labels": [{"theme_id": "not_in_taxonomy", "confidence": 0.9,
                        "evidence_quote": "generative AI"}],
            "new_themes": [],
        }
        labels, _, warnings = labeling.validate_output(output, post, self.themes)
        self.assertEqual(labels, [])
        self.assertTrue(warnings)

    def test_new_theme_is_created_and_used(self):
        post = "Throwback to three amazing days at React India!"
        output = {
            "labels": [{"theme_id": "react_community", "confidence": 0.9,
                        "evidence_quote": "React India"}],
            "new_themes": [{
                "theme_id": "react_community",
                "label": "React community",
                "description": "Developer community events",
                "include_examples": "React India",
                "exclude_examples": "",
            }],
        }
        labels, new_themes, warnings = labeling.validate_output(output, post, self.themes)
        self.assertEqual(labels[0]["theme_id"], "react_community")
        self.assertTrue(labels[0]["is_new_theme"])
        self.assertEqual(new_themes[0]["theme_id"], "react_community")
        self.assertEqual(warnings, [])

    def test_unreferenced_new_theme_is_not_saved(self):
        post = "A normal post."
        output = {
            "labels": [],
            "new_themes": [{"theme_id": "unused", "label": "Unused"}],
        }
        labels, new_themes, _ = labeling.validate_output(output, post, self.themes)
        self.assertEqual(labels, [])
        self.assertEqual(new_themes, [])

    def test_slugify(self):
        self.assertEqual(labeling.slugify("React Community!"), "react_community")

    def test_label_post_parses_json_response(self):
        payload = {
            "labels": [{"theme_id": "ai_automation", "confidence": 0.9,
                        "evidence_quote": "generative AI"}],
            "new_themes": [],
        }

        class Message:
            content = json.dumps(payload)

        class Choice:
            message = Message()

        class Response:
            choices = [Choice()]

        class Completions:
            def create(self, **kwargs):
                self.kwargs = kwargs
                return Response()

        class Chat:
            completions = Completions()

        class Client:
            chat = Chat()

        client = Client()
        result = labeling.label_post(client, "We use generative AI.", self.themes)
        self.assertEqual(result, payload)
        self.assertEqual(client.chat.completions.kwargs["model"], labeling.MODEL)
        self.assertEqual(
            client.chat.completions.kwargs["response_format"],
            {"type": "json_object"},
        )
        self.assertEqual(
            client.chat.completions.kwargs["extra_body"],
            {"thinking": {"type": "disabled"}},
        )

    def test_new_theme_is_added_to_taxonomy(self):
        taxonomy = labeling.pd.read_csv(labeling.TAXONOMY, dtype=str, keep_default_na=False)
        updated = labeling.add_new_themes(taxonomy, [{
            "theme_id": "react_community",
            "label": "React community",
            "description": "Developer community events",
            "include_examples": "React India",
            "exclude_examples": "",
        }])
        row = updated[updated["theme_id"] == "react_community"].iloc[0]
        self.assertEqual(row["source"], "llm")
        self.assertEqual(row["taxonomy_id"], labeling.TAXONOMY_ID)
        effective = labeling._effective_taxonomy(updated, labeling.TAXONOMY_ID)
        self.assertIn("react_community", set(effective["theme_id"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
