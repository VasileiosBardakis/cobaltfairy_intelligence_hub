import csv
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_csv(name):
    with (ROOT / "data" / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def normalize(text):
    return re.sub(r"\s+", " ", str(text)).strip().lower()


class TestGeneratedThemeLabels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.posts = {row["post_id"]: row for row in read_csv("social_posts.csv")}
        cls.labels = read_csv("theme_labels.csv")
        cls.taxonomy = {
            row["theme_id"] for row in read_csv("theme_taxonomy.csv")
            if row["active"].lower() == "true"
        }

    def test_columns(self):
        self.assertEqual(
            list(self.labels[0].keys()),
            [
                "post_id", "taxonomy_id", "version", "theme_id", "confidence",
                "evidence_quote", "is_new_theme", "label_source", "model",
                "prompt_version", "created_at",
            ],
        )

    def test_every_post_has_a_label(self):
        labelled = {row["post_id"] for row in self.labels}
        self.assertEqual(labelled, set(self.posts))
        self.assertTrue(all(row["label_source"] == "llm" for row in self.labels))
        self.assertTrue(all(row["created_at"] for row in self.labels))

    def test_theme_ids_exist(self):
        used = {row["theme_id"] for row in self.labels}
        self.assertTrue(used)
        self.assertTrue(used.issubset(self.taxonomy))

    def test_quotes_are_grounded(self):
        for row in self.labels:
            post = normalize(self.posts[row["post_id"]]["text"])
            self.assertIn(normalize(row["evidence_quote"]), post, row["theme_id"])

    def test_confidence_and_duplicates(self):
        self.assertTrue(all(0 <= float(row["confidence"]) <= 1 for row in self.labels))
        keys = [(row["post_id"], row["theme_id"]) for row in self.labels]
        self.assertEqual(len(keys), len(set(keys)))

    def test_key_examples(self):
        by_post = {}
        for row in self.labels:
            by_post.setdefault(row["post_id"], set()).add(row["theme_id"])

        self.assertTrue({
            "ai_automation",
            "peak_season_bfcm",
        }.issubset(by_post["fb-mailchimp-2026-11-17-1"]))
        self.assertTrue({
            "peak_season_bfcm",
            "product_positioning",
        }.issubset(by_post["fb-brevo-2026-11-13-1"]))
        self.assertIn("discount_promotion", by_post["fb-mailerlite-2026-11-17-1"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
