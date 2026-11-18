import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pricing

DB = ROOT / "data" / "intel.db"


class TestPricingCoverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DB.exists():
            raise unittest.SkipTest("data/intel.db is not available")
        con = sqlite3.connect(DB)
        cls.baseline, cls.current = pricing.load_pricing(con)
        con.close()
        cls.changes = pricing.compare_pricing(cls.baseline, cls.current)
        cls.coverage = pricing.coverage_summary(
            cls.baseline, cls.current, cls.changes
        ).set_index("Provider")

    def test_platform_and_point_coverage(self):
        self.assertEqual(len(self.current), 39)
        self.assertEqual(
            set(self.current["platform"]),
            {
                "AWeber", "ActiveCampaign", "Brevo", "Constant Contact",
                "Mailchimp", "MailerLite", "Moosend", "Omnisend",
            },
        )
        self.assertEqual(set(self.coverage.index), set(self.current["platform"]))

    def test_current_rows_are_complete_and_unique(self):
        self.assertTrue(self.current["price"].notna().all())
        self.assertTrue(self.current["source_url"].astype(str).str.strip().ne("").all())
        self.assertTrue(self.current["captured_at"].astype(str).str.strip().ne("").all())
        self.assertFalse(
            self.current.duplicated(
                ["platform", "plan", "current_tier", "tier_basis"]
            ).any()
        )

    def test_coverage_counts(self):
        self.assertEqual(int(self.coverage.loc["AWeber", "Unmatched baseline points"]), 2)
        self.assertEqual(int(self.coverage.loc["AWeber", "Captured points"]), 4)
        self.assertEqual(int(self.coverage.loc["Brevo", "Captured points"]), 5)
        self.assertEqual(int(self.coverage.loc["Brevo", "Unmatched baseline points"]), 0)
        self.assertEqual(
            int(self.coverage["Unmatched baseline points"].sum()), 2
        )
        for provider in [
            "ActiveCampaign", "Constant Contact", "Mailchimp", "MailerLite",
            "Moosend", "Omnisend",
        ]:
            self.assertEqual(
                int(self.coverage.loc[provider, "Unmatched baseline points"]), 0,
                provider,
            )

    def test_tier_mismatches_are_flagged(self):
        expected = {
            "ActiveCampaign": 4,
            "Constant Contact": 3,
            "Moosend": 1,
            "Brevo": 5,
            "Mailchimp": 0,
            "MailerLite": 0,
            "AWeber": 0,
            "Omnisend": 0,
        }
        for provider, count in expected.items():
            self.assertEqual(
                int(self.coverage.loc[provider, "Tier mismatches"]), count,
                provider,
            )

    def test_nearest_tiers_are_marked_as_mismatches(self):
        rows = self.changes[
            (self.changes["platform"] == "ActiveCampaign")
            & (self.changes["current_tier"] == 1000)
        ]
        self.assertTrue(rows["tier_mismatch"].all())
        constant = self.changes[
            (self.changes["platform"] == "Constant Contact")
            & (self.changes["current_tier"] == 25000)
        ]
        self.assertTrue(constant["tier_mismatch"].all())
        exact = self.changes[
            (self.changes["platform"] == "ActiveCampaign")
            & (self.changes["current_tier"] == 20000)
        ]
        self.assertFalse(exact["tier_mismatch"].any())


if __name__ == "__main__":
    unittest.main(verbosity=2)
