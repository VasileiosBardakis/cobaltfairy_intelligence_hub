# SYNTHETIC SOCIAL FIXTURE — NOT REAL EVIDENCE

This folder is a test fixture only.

It contains fictional social posts for three fictional email-marketing brands:

- AlphaMail
- BetaSend
- GammaMail

These brands are invented. They are not Mailchimp, Brevo, MailerLite, or any real company. Nothing here is a real competitor statement, real post, real price, or real metric.

## Why this exists

The real social dataset is thin: 11 captured public Facebook posts, no LinkedIn/Instagram, and only one MailerLite post. That is not enough to exercise trend detection, theme grouping, coverage handling, or the UI at volume.

This fixture provides 120 synthetic posts across 3 fictional brands, 3 platforms (Facebook, Instagram, LinkedIn), and the three-month window 2026-08-18 to 2026-11-18. It is for pipeline scale and UI demonstration only.

LinkedIn posts are present in all three months for each brand. The app also builds synthetic cross-source signals with synthetic pricing, plus verified, inferential, and unsupported claims, so the cross-source and error-log views are exercised in the demo.

## Files

- `social_posts_synthetic.csv` — 120 synthetic posts.
- `social_coverage_synthetic.csv` — coverage rows for the synthetic brands/platforms.
- `generate_synthetic.py` — deterministic generator (seed `20261118`).

## Labels and separation

Every synthetic row carries:

- `data_origin=synthetic_demo`
- `dataset_label=synthetic_demo_v1`
- `is_synthetic=true`
- `brand_type=fictional`
- `source_type=synthetic_fixture`
- `source_url` under `https://example.com/synthetic-social/...`
- `synthetic_theme`, `synthetic_subtheme`, `synthetic_relevance`

The real data lives in `data/social_posts.csv` and `data/social_coverage.csv` and does not carry these labels. Do not merge the two files. Do not load this fixture into the real `social_posts` table. Load it separately, behind a synthetic demo mode or a separate table, and show a visible synthetic banner in the UI.

## Regenerate

From the repo root:

```powershell
.\.venv\Scripts\python.exe fixtures\synthetic_social\generate_synthetic.py
```

The generator is deterministic and uses only the Python standard library.

## App wiring

The app loads this fixture only in synthetic social demo mode. It is built in memory by `synthetic_demo.py`; it is not written to `intel.db` and is never mixed into the real `social_posts` or `signals` tables.

- The app defaults to synthetic social demo mode.
- The top-right button switches to real social data.
- Synthetic mode keeps CF and pricing comparison from the real captured data, and adds synthetic cross-source signals with synthetic pricing.
- A persistent banner labels the synthetic demo.

The loader must keep requiring `data_origin=synthetic_demo` and keep synthetic and real counts separate.

## Do not

- Do not present these posts as real competitor activity.
- Do not use these posts to support real FairyMail conclusions.
- Do not mix these rows with `data/social_posts.csv`.
- Do not remove the labels.
