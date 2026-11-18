import contextlib
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import briefs


def signal(**overrides):
    data = {
        "signal_id": "s1",
        "signal_type": "social_theme",
        "title": "Test signal",
        "entity": "test",
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
        "summary": "Test summary",
        "status": "candidate",
        "confidence": 0.9,
        "coverage_note": "Test coverage",
        "rule_version": "test-v1",
        "created_at": "2026-02-01T00:00:00+00:00",
    }
    data.update(overrides)
    return data


def evidence(quote="generative AI"):
    return [{
        "evidence_id": "social:p1",
        "evidence_type": "social_post",
        "quote": quote,
        "role": "supporting",
    }]


def pricing_evidence():
    return [
        {
            "evidence_id": "pricing_baseline:MailerLite:Advanced:500",
            "evidence_type": "pricing_baseline",
            "quote": "MailerLite Advanced: $20/month at 500 subscribers",
            "role": "supporting",
        },
        {
            "evidence_id": "pricing:MailerLite:Power:500:subscribers",
            "evidence_type": "pricing_current",
            "quote": "MailerLite Power: $25/month at 500 subscribers",
            "role": "supporting",
        },
        {
            "evidence_id": "pricing_rename:MailerLite:Advanced:Power:500:subscribers",
            "evidence_type": "pricing_rename",
            "quote": "Plan renamed from Advanced to Power; Advanced is not a separate current plan.",
            "role": "supporting",
        },
    ]


class TestBriefChecker(unittest.TestCase):
    def test_verified_claim(self):
        output = {"positioning": "Test", "claims": [{
            "claim": "The post mentions generative AI.",
            "evidence_ids": ["social:p1"],
            "quote": "generative AI",
        }]}
        claims, status, _ = briefs.check_output(output, signal(), evidence())
        self.assertEqual(claims[0]["verification_status"], "verified")
        self.assertEqual(status, "auto_checked")

    def test_inferential_claim(self):
        output = {"positioning": "Test", "claims": [{
            "claim": "The post is about AI.",
            "evidence_ids": ["social:p1"],
            "quote": "",
        }]}
        claims, _, _ = briefs.check_output(output, signal(), evidence())
        self.assertEqual(claims[0]["verification_status"], "inferential")

    def test_bad_quote_is_unsupported(self):
        output = {"positioning": "Test", "claims": [{
            "claim": "The post mentions AI.",
            "evidence_ids": ["social:p1"],
            "quote": "invented quote",
        }]}
        claims, _, _ = briefs.check_output(output, signal(), evidence())
        self.assertEqual(claims[0]["verification_status"], "unsupported")

    def test_unknown_evidence_is_unsupported(self):
        output = {"positioning": "Test", "claims": [{
            "claim": "The post mentions AI.",
            "evidence_ids": ["missing"],
            "quote": "generative AI",
        }]}
        claims, _, _ = briefs.check_output(output, signal(), evidence())
        self.assertEqual(claims[0]["verification_status"], "unsupported")

    def test_trend_language_under_three_posts_is_unsupported(self):
        output = {"positioning": "Test", "claims": [{
            "claim": "AI messaging is growing.",
            "evidence_ids": ["social:p1"],
            "quote": "generative AI",
        }]}
        claims, _, _ = briefs.check_output(
            output, signal(status="insufficient"), evidence()
        )
        self.assertEqual(claims[0]["verification_status"], "unsupported")
        self.assertIn("trend language", claims[0]["checker_note"])

    def test_pricing_plan_name_is_not_trend_language(self):
        output = {"positioning": "Test", "claims": [{
            "claim": "Growing Business costs $10.",
            "evidence_ids": ["social:p1"],
            "quote": "generative AI",
        }]}
        claims, _, _ = briefs.check_output(
            output, signal(signal_type="pricing_change"), evidence()
        )
        self.assertEqual(claims[0]["verification_status"], "verified")

    def test_renamed_plan_cannot_coexist(self):
        output = {"positioning": "Test", "claims": [{
            "claim": "The Advanced plan remains at $20.",
            "evidence_ids": ["pricing_baseline:MailerLite:Advanced:500"],
            "quote": "MailerLite Advanced: $20/month at 500 subscribers",
        }]}
        claims, _, _ = briefs.check_output(
            output, signal(signal_type="pricing_change"), pricing_evidence()
        )
        self.assertEqual(claims[0]["verification_status"], "unsupported")
        self.assertIn("renamed plan", claims[0]["checker_note"])

    def test_unqualified_old_plan_claim_is_unsupported(self):
        output = {"positioning": "Test", "claims": [{
            "claim": "Advanced costs $20 per month.",
            "evidence_ids": ["pricing_baseline:MailerLite:Advanced:500"],
            "quote": "MailerLite Advanced: $20/month at 500 subscribers",
        }]}
        claims, _, _ = briefs.check_output(
            output, signal(signal_type="pricing_change"), pricing_evidence()
        )
        self.assertEqual(claims[0]["verification_status"], "unsupported")

    def test_baseline_qualified_old_plan_claim_is_allowed(self):
        output = {"positioning": "Test", "claims": [{
            "claim": "The baseline Advanced plan was $20 per month.",
            "evidence_ids": ["pricing_baseline:MailerLite:Advanced:500"],
            "quote": "MailerLite Advanced: $20/month at 500 subscribers",
        }]}
        claims, _, _ = briefs.check_output(
            output, signal(signal_type="pricing_change"), pricing_evidence()
        )
        self.assertEqual(claims[0]["verification_status"], "verified")

    def test_explicit_rename_claim_is_allowed(self):
        output = {"positioning": "Test", "claims": [{
            "claim": "Advanced was renamed to Power and is not a separate current plan.",
            "evidence_ids": [
                "pricing_rename:MailerLite:Advanced:Power:500:subscribers"
            ],
            "quote": "Plan renamed from Advanced to Power; Advanced is not a separate current plan.",
        }]}
        claims, _, _ = briefs.check_output(
            output, signal(signal_type="pricing_change"), pricing_evidence()
        )
        self.assertEqual(claims[0]["verification_status"], "verified")

    def test_renamed_plan_positioning_needs_review(self):
        output = {
            "positioning": "Power is higher priced while Advanced remains available.",
            "claims": [],
        }
        _, status, note = briefs.check_output(
            output, signal(signal_type="pricing_change"), pricing_evidence()
        )
        self.assertEqual(status, "needs_review")
        self.assertIn("renamed plan", note)


class TestGenerateBriefs(unittest.TestCase):
    def test_generate_and_store(self):
        payload = {
            "positioning": "Grounded positioning.",
            "claims": [{
                "claim": "The post mentions generative AI.",
                "evidence_ids": ["social:p1"],
                "quote": "generative AI",
            }, {
                "claim": "The post is about AI.",
                "evidence_ids": ["social:p1"],
                "quote": "",
            }],
        }

        class Message:
            content = json.dumps(payload)

        class Choice:
            message = Message()

        class Response:
            choices = [Choice()]

        class Completions:
            def create(self, **kwargs):
                return Response()

        class Chat:
            completions = Completions()

        class Client:
            chat = Chat()

        with tempfile.TemporaryDirectory() as folder:
            db_path = Path(folder) / "test.db"
            con = sqlite3.connect(db_path)
            con.executescript("""
                CREATE TABLE signals (
                    signal_id TEXT PRIMARY KEY, signal_type TEXT, title TEXT,
                    entity TEXT, period_start TEXT, period_end TEXT, summary TEXT,
                    status TEXT, confidence REAL, coverage_note TEXT,
                    rule_version TEXT, created_at TEXT
                );
                CREATE TABLE signal_evidence (
                    signal_id TEXT, evidence_id TEXT, evidence_type TEXT,
                    quote TEXT, role TEXT, verified INTEGER
                );
            """)
            sig = signal()
            con.execute(
                "INSERT INTO signals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                list(sig.values()),
            )
            con.execute(
                "INSERT INTO signal_evidence VALUES (?, ?, ?, ?, ?, 1)",
                ("s1", "social:p1", "social_post", "generative AI", "supporting"),
            )
            con.commit()
            con.close()

            with contextlib.redirect_stdout(io.StringIO()):
                briefs.generate_briefs(db_path=db_path, client=Client())

            con = sqlite3.connect(db_path)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM briefs").fetchone()[0], 1)
            statuses = {
                row[0] for row in con.execute("SELECT verification_status FROM claims")
            }
            self.assertEqual(statuses, {"verified", "inferential"})
            con.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
