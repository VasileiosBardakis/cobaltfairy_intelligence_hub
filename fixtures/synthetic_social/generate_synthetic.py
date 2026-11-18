import csv
import random
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).parent
SEED = 20261118
START = date(2026, 8, 18)
END = date(2026, 11, 18)
CAPTURED = date(2026, 11, 18)

BRANDS = [
    ("AlphaMail", "alphamail"),
    ("BetaSend", "betasend"),
    ("GammaMail", "gammamail"),
]

PLATFORMS = [
    ("Meta", "Facebook", "facebook"),
    ("Meta", "Instagram", "instagram"),
    ("LinkedIn", "LinkedIn", "linkedin"),
]

MONTHS = [
    (date(2026, 8, 18), date(2026, 9, 17), 12),
    (date(2026, 9, 18), date(2026, 10, 17), 13),
    (date(2026, 10, 18), date(2026, 11, 18), 15),
]

TEMPLATES_M1 = [
    ("ai_automation", "AI assistant", "Our new AI assistant drafts subject lines and preview text in seconds. {brand} customers can test three variants before lunch."),
    ("ai_automation", "Automation workflows", "Automation should not feel robotic. Build a welcome flow, a browse-abandon flow, and a winback flow once, then let {brand} handle the timing."),
    ("ai_automation", "Generative copy", "We added a generative AI helper to our campaign builder. It suggests copy, but you stay in control of every send."),
    ("customer_data_personalization", "Segmentation", "Segmentation is not a one-time setup. Start with three groups: first-time buyers, repeat buyers, and lapsed customers."),
    ("customer_data_personalization", "Behavioral targeting", "Personalization works better when it is based on behavior, not just a first name. {brand} now supports behavioral segments."),
    ("email_sms_multichannel", "Email plus SMS", "Email and SMS are better together. Use email for the story, SMS for the nudge, and one calendar for both."),
    ("email_sms_multichannel", "Channel testing", "A simple multichannel test: send the same offer by email and SMS to two small segments, then compare revenue per recipient."),
    ("product_positioning", "Right message", "The right message to the right person at the right time. That is the whole game. {brand} keeps the workflow simple."),
    ("brand_creative", "Template redesign", "Behind the scenes: our design team rebuilt the campaign template library around fewer, clearer layouts."),
    ("community_events", "Virtual roundtable", "We are hosting a small virtual roundtable for lifecycle marketers next month. Bring one workflow you want to improve."),
    ("product_positioning", "Ease of use", "No-code onboarding, clear reporting, and a send calendar your team can actually read. That is the {brand} approach."),
    ("community_events", "Conference", "Our team is at GrowthStack Summit this week. Say hello if you are nearby."),
]

TEMPLATES_M2 = [
    ("customer_data_personalization", "Core segments", "Three segments worth building this month: high-intent browsers, one-time buyers, and customers who have not opened in 90 days."),
    ("customer_data_personalization", "RFM", "RFM does not have to be complicated. Recency, frequency, and monetary value can guide your next three campaigns."),
    ("email_sms_multichannel", "SMS use cases", "SMS is not a replacement for email. It is a second touch for time-sensitive moments like cart recovery and delivery updates."),
    ("email_sms_multichannel", "Measurement", "Test one SMS nudge against one email reminder. Measure revenue per recipient, not open rate."),
    ("product_positioning", "Customer story", "A mid-market retailer used {brand} to consolidate four tools into one send calendar. Fewer handoffs, clearer reporting."),
    ("customer_data_personalization", "Data hygiene", "Personalization at scale starts with clean data. Merge duplicates, standardize fields, and define your core segments."),
    ("product_positioning", "No developer needed", "Your team should not need a developer to build a welcome flow. {brand} keeps the common lifecycle journeys in the UI."),
    ("brand_creative", "Customer stories", "A customer story is more useful than a feature list. We are collecting stories about teams that simplified their stack."),
    ("community_events", "Onboarding clinic", "We are running a live onboarding clinic every Thursday. Bring your campaign calendar and leave with a cleaner flow."),
    ("ai_automation", "Busywork", "AI is most useful when it removes busywork: subject line variants, send-time suggestions, and first-draft copy."),
    ("email_sms_multichannel", "Peak planning", "Peak season planning starts earlier than you think. Map your email and SMS calendar before the offers are final."),
    ("product_positioning", "Reporting", "Good reporting answers three questions: what changed, why it changed, and what to test next."),
]

TEMPLATES_M3 = [
    ("peak_season_bfcm", "BFCM checklist", "The BFCM checklist: clean your list, refresh your segments, prepare three offers, and schedule the reminder emails now."),
    ("peak_season_bfcm", "Sequence", "Peak season is not one send. It is a sequence: tease, launch, remind, extend, and thank."),
    ("peak_season_bfcm", "VIP segment", "Your best customers should not get the same BFCM message as everyone else. Build a VIP segment before the rush."),
    ("email_sms_multichannel", "Deadline channel", "During BFCM, email carries the detail and SMS carries the deadline. Keep both on one calendar."),
    ("discount_promotion", "Annual offer", "Annual plans are 25% off this week. Lock in the rate, keep the same workflow, and skip the renewal surprise."),
    ("discount_promotion", "Deadline", "A limited-time offer works better when the deadline is real. Pick one end date and put it in every channel."),
    ("discount_promotion", "Black Friday", "Our Black Friday offer is live: save on annual plans and keep the full feature set. No promo code required."),
    ("ai_automation", "AI drafting", "Use AI to draft the first version of your BFCM emails, then edit for your brand voice. Speed matters, but judgment matters more."),
    ("customer_data_personalization", "BFCM segments", "Build three BFCM segments: ready-to-buy, needs-a-nudge, and do-not-discount. Treat them differently."),
    ("product_positioning", "Calm setup", "The best peak-season setup is the one your team can run without a war room. Simple calendar, clear owners, one source of truth."),
    ("peak_season_bfcm", "Cyber Monday", "Cyber Monday is not a rerun of Black Friday. Change the offer, the angle, or the audience, or skip it."),
    ("brand_creative", "Holiday templates", "Our holiday template pack is live. Fewer layouts, stronger hierarchy, and room for your own photography."),
    ("community_events", "Planning session", "Thank you to everyone who joined our peak-season planning session. The recording and checklist are in the community."),
    ("product_positioning", "Hiring", "We are hiring a lifecycle marketing lead to help customers build calmer, clearer campaigns. Details on our careers page."),
    ("brand_creative", "Report redesign", "Our team spent the week rebuilding the report view around three questions marketers actually ask."),
    ("community_events", "InboxCon", "We are at InboxCon this week. Come by the booth and talk about deliverability, segmentation, or BFCM stress."),
]

TEMPLATES_BY_MONTH = [TEMPLATES_M1, TEMPLATES_M2, TEMPLATES_M3]
CORE_THEMES = {
    "ai_automation",
    "peak_season_bfcm",
    "email_sms_multichannel",
    "customer_data_personalization",
    "discount_promotion",
    "product_positioning",
}

POST_FIELDS = [
    "post_id",
    "brand",
    "brand_type",
    "network",
    "platform",
    "posted_at",
    "date_display",
    "text",
    "source_url",
    "source_type",
    "captured_at",
    "notes",
    "data_origin",
    "dataset_label",
    "is_synthetic",
    "synthetic_theme",
    "synthetic_subtheme",
    "synthetic_relevance",
]

COVERAGE_FIELDS = [
    "brand",
    "brand_type",
    "network",
    "platform",
    "status",
    "posts_captured",
    "window_start",
    "window_end",
    "captured_at",
    "notes",
    "data_origin",
    "dataset_label",
    "is_synthetic",
]


def random_dates(rng, start, end, count):
    span = (end - start).days
    offsets = rng.sample(range(span + 1), count)
    return sorted(start + timedelta(days=offset) for offset in offsets)


def build_rows():
    rows = []
    coverage = []

    for brand_index, (brand, brand_slug) in enumerate(BRANDS):
        rng = random.Random(SEED + brand_index)
        sequence = 1
        brand_rows = []

        for month_index, (month_start, month_end, count) in enumerate(MONTHS):
            pool = TEMPLATES_BY_MONTH[month_index]
            chosen = rng.sample(pool, min(count, len(pool)))
            while len(chosen) < count:
                chosen.append(rng.choice(pool))
            rng.shuffle(chosen)

            dates = random_dates(rng, month_start, month_end, count)

            for offset, (theme, subtheme, template) in enumerate(chosen):
                network, platform, platform_slug = PLATFORMS[
                    (offset + brand_index) % len(PLATFORMS)
                ]
                posted = dates[offset]
                post_id = (
                    f"syn-{brand_slug}-{platform_slug}-"
                    f"{posted.isoformat()}-{sequence:03d}"
                )
                sequence += 1
                brand_rows.append(
                    {
                        "post_id": post_id,
                        "brand": brand,
                        "brand_type": "fictional",
                        "network": network,
                        "platform": platform,
                        "posted_at": posted.isoformat(),
                        "date_display": posted.strftime("%b %d"),
                        "text": template.format(brand=brand),
                        "source_url": (
                            "https://example.com/synthetic-social/"
                            f"{brand_slug}/{post_id}"
                        ),
                        "source_type": "synthetic_fixture",
                        "captured_at": CAPTURED.isoformat(),
                        "notes": (
                            "Synthetic fixture; fictional brand; not real evidence; "
                            "for pipeline demo only."
                        ),
                        "data_origin": "synthetic_demo",
                        "dataset_label": "synthetic_demo_v1",
                        "is_synthetic": "true",
                        "synthetic_theme": theme,
                        "synthetic_subtheme": subtheme,
                        "synthetic_relevance": (
                            "core" if theme in CORE_THEMES else "low"
                        ),
                    }
                )

        rows.extend(brand_rows)

        for network, platform, _ in PLATFORMS:
            count = sum(1 for row in brand_rows if row["platform"] == platform)
            coverage.append(
                {
                    "brand": brand,
                    "brand_type": "fictional",
                    "network": network,
                    "platform": platform,
                    "status": "synthetic_demo",
                    "posts_captured": count,
                    "window_start": START.isoformat(),
                    "window_end": END.isoformat(),
                    "captured_at": CAPTURED.isoformat(),
                    "notes": (
                        "Synthetic fixture coverage; fictional brand; "
                        "not real evidence."
                    ),
                    "data_origin": "synthetic_demo",
                    "dataset_label": "synthetic_demo_v1",
                    "is_synthetic": "true",
                }
            )

    return rows, coverage


def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    rows, coverage = build_rows()

    assert len(rows) == 120
    assert len({row["post_id"] for row in rows}) == len(rows)
    assert len({row["brand"] for row in rows}) == 3
    assert len({row["platform"] for row in rows}) == 3
    assert all(row["data_origin"] == "synthetic_demo" for row in rows)
    assert all(row["is_synthetic"] == "true" for row in rows)
    assert all(row["brand_type"] == "fictional" for row in rows)
    assert all(row["text"] and row["source_url"] for row in rows)
    assert all(
        START <= date.fromisoformat(row["posted_at"]) <= END for row in rows
    )
    assert len(coverage) == 9
    assert sum(row["posts_captured"] for row in coverage) == len(rows)

    write_csv(OUT / "social_posts_synthetic.csv", POST_FIELDS, rows)
    write_csv(OUT / "social_coverage_synthetic.csv", COVERAGE_FIELDS, coverage)

    print(f"posts: {len(rows)}")
    print(f"coverage rows: {len(coverage)}")
    for brand, _ in BRANDS:
        print(brand, sum(1 for row in rows if row["brand"] == brand))


if __name__ == "__main__":
    main()
