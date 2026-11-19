import contextlib
import io
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import signals

DB = ROOT / "data" / "intel.db"


class TestSignals(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with contextlib.redirect_stdout(io.StringIO()):
            signals.generate_signals()
        cls.con = sqlite3.connect(DB)
        cls.con.row_factory = sqlite3.Row

    @classmethod
    def tearDownClass(cls):
        cls.con.close()

    def one(self, sql, params=()):
        return self.con.execute(sql, params).fetchone()

    def test_schema(self):
        tables = {
            row["name"] for row in self.con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        self.assertTrue({"signals", "signal_evidence"} <= tables)

    def test_signal_types(self):
        types = {
            row["signal_type"] for row in self.con.execute(
                "SELECT DISTINCT signal_type FROM signals"
            )
        }
        self.assertEqual(
            types,
            {"social_theme", "pricing_change", "cf_market", "cross_source"},
        )
        self.assertEqual(
            self.one("SELECT COUNT(*) AS n FROM signals WHERE signal_type='coverage_gap'")["n"],
            0,
        )
        self.assertEqual(
            self.one("SELECT COUNT(*) AS n FROM social_coverage")["n"], 9
        )
        self.assertEqual(
            self.one("SELECT COUNT(*) AS n FROM social_posts")["n"], 128
        )
        self.assertEqual(
            self.one(
                "SELECT COUNT(*) AS n FROM social_posts WHERE platform='LinkedIn'"
            )["n"],
            117,
        )

    def test_social_thresholds(self):
        peak = self.one(
            "SELECT status, summary FROM signals WHERE signal_type='social_theme' "
            "AND entity='peak_season_bfcm'"
        )
        discount = self.one(
            "SELECT status, summary FROM signals WHERE signal_type='social_theme' "
            "AND entity='discount_promotion'"
        )
        self.assertEqual(peak["status"], "candidate")
        self.assertEqual(discount["status"], "candidate")
        self.assertNotIn("trend", discount["summary"].lower())
        self.assertEqual(
            self.one(
                "SELECT COUNT(*) AS n FROM signals "
                "WHERE signal_type='social_theme' AND status='insufficient'"
            )["n"],
            0,
        )

    def test_pricing_signals(self):
        self.assertGreaterEqual(
            self.one("SELECT COUNT(*) AS n FROM signals WHERE signal_type='pricing_change'")["n"],
            8,
        )
        for title in [
            "MailerLite changes Comfort price at 500 subscribers",
            "Brevo renames Business to Standard at 5000 emails",
            "Brevo renames Business to Standard at 20000 emails",
            "Brevo launches Professional at 150000 emails",
            "ActiveCampaign changes Pro price at 20000 subscribers",
            "Constant Contact changes Lite price at 25000 subscribers",
        ]:
            self.assertIsNotNone(self.one(
                "SELECT 1 FROM signals WHERE title=?", (title,)
            ), title)
        self.assertIsNotNone(self.one(
            "SELECT 1 FROM signals WHERE entity='Brevo' "
            "AND coverage_note LIKE '%differs from baseline%'"
        ))
        self.assertIsNone(self.one(
            "SELECT 1 FROM signals WHERE title LIKE '%at 500 emails%'"
        ))
        for title in [
            "ActiveCampaign changes Pro price at 1000 subscribers",
            "Constant Contact changes Lite price at 25000 subscribers",
        ]:
            row = self.one(
                "SELECT status, confidence FROM signals WHERE title=?", (title,)
            )
            self.assertEqual(row["status"], "inferential", title)
            self.assertLess(row["confidence"], 1.0, title)
        exact = self.one(
            "SELECT status, confidence FROM signals "
            "WHERE title='ActiveCampaign changes Pro price at 20000 subscribers'"
        )
        self.assertEqual(exact["status"], "candidate")
        self.assertEqual(exact["confidence"], 1.0)
        rename = self.one(
            "SELECT quote FROM signal_evidence e JOIN signals s "
            "ON s.signal_id=e.signal_id WHERE s.title="
            "'MailerLite changes Power price at 500 subscribers' "
            "AND e.evidence_type='pricing_rename'"
        )
        self.assertIsNotNone(rename)
        self.assertIn("Advanced", rename["quote"])
        self.assertIn("Power", rename["quote"])

    def test_cross_source(self):
        status = {
            row["entity"]: row["status"] for row in self.con.execute(
                "SELECT entity, status FROM signals WHERE signal_type='cross_source'"
            )
        }
        self.assertEqual(status["Mailchimp"], "inferential")
        self.assertEqual(status["Brevo"], "inferential")
        self.assertEqual(status["MailerLite"], "inferential")
        mailchimp = self.one(
            "SELECT summary FROM signals WHERE signal_type='cross_source' "
            "AND entity='Mailchimp'"
        )
        self.assertIn("no causal link", mailchimp["summary"].lower())

    def test_cf_signals(self):
        western = self.one(
            "SELECT status, coverage_note FROM signals WHERE signal_type='cf_market' "
            "AND entity='Western'"
        )
        regency = self.one(
            "SELECT status FROM signals WHERE signal_type='cf_market' AND entity='Regency'"
        )
        self.assertEqual(western["status"], "insufficient")
        self.assertIn("secondary mapping", western["coverage_note"].lower())
        self.assertEqual(regency["status"], "candidate")

    def test_evidence_is_present(self):
        self.assertEqual(
            self.one(
                "SELECT COUNT(*) AS n FROM signals s WHERE NOT EXISTS "
                "(SELECT 1 FROM signal_evidence e WHERE e.signal_id=s.signal_id)"
            )["n"],
            0,
        )
        self.assertEqual(
            self.one(
                "SELECT COUNT(*) AS n FROM signal_evidence "
                "WHERE quote IS NULL OR quote='' OR verified != 1"
            )["n"],
            0,
        )

    def test_signal_ids_are_stable(self):
        before = {row["signal_id"] for row in self.con.execute("SELECT signal_id FROM signals")}
        with contextlib.redirect_stdout(io.StringIO()):
            signals.generate_signals()
        after = {row["signal_id"] for row in self.con.execute("SELECT signal_id FROM signals")}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main(verbosity=2)
