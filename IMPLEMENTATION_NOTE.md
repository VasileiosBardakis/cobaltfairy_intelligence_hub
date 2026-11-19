# Implementation note

## Problem

As the docx said, the problem is the manual effort required to transform information into useful market intelligence while still having a human make those decisions. So this is a tool to help an analyst make decisions, NOT an autonomous agent.

## Priorities

- Built the deterministic core first: ingest, mapping, pricing diffs, signals.
- Give every signal a stable ID, status, coverage note, and evidence rows.
- Use AI for one meaningful task (theme labelling), with briefs as a constrained
  second layer.
- Skip live collection, auth, scheduling, and a review workflow.

## Decisions

- Python, pandas, SQLite, Streamlit; one database, simple for a task this size.
- Mappings live in `data/mappings.csv`, not in code.
- `ingest.py` asserts counts, uniqueness, and known values.
- `pricing.py` flags plan renames and tier mismatches.
- `signals.py` applies fixed thresholds and stable SHA1 IDs.
- `briefs.py` skips unchanged inputs by hash and runs a rule checker.
- The UI only reads SQLite.

## AI use

Used for theme labelling (taxonomy + post to a label and exact quote; bad themes,
quotes, and confidence are dropped) and briefs (signal + evidence to positioning
and claims; evidence IDs and exact quotes required). Both use DeepSeek flash,
temperature 0, JSON mode, thinking disabled, batch only. Used this model because it is extremely cheap and good, I code with it also. In a real case scenario though where we have funds for better models, the decision would be different.

Not used for ingestion, mappings, joins, pricing, thresholds, IDs, evidence
assembly, checking, or the UI. Those are deterministic and testable.

Raw session exports are in `ai_conversations/`;

## Assumptions

- K-lytics is the market benchmark; manual mappings are the bridge.
- CF commercial values are synthetic.
- Pricing baseline is Sep 2025; current captures are Nov 2026.
- Public Facebook and LinkedIn posts sourced from the companies' public pages;
- Theme threshold 3 posts; CF threshold 5 same-title observations.

## Limits

*Data Constraints* 
- Coverage is partial: 11 Facebook and 117 LinkedIn public posts, sourced directly from the companies' public pages. Some LinkedIn dates are approximate where the page showed relative age. Docx said that this data was given in the dropbox link however it wasn't, so we sourced it manually from linkedin and automatically from facebook (as much as we could without login).
- Only two K-lytics months were supplied, so the CF comparison is
month-over-month, not a trend. Two CF categories also have fewer than five  same-title observations and stay `insufficient`.
- CF commercial values are synthetic. The signal notes say so, so the comparison
is not read as real performance.
- The pricing baseline is Sep 2025 and current tiers often differ. Those rows are  marked `inferential` and carry the mismatch, rather than being treated as
like-for-like.

*Prototype Constraints*
- The database is a snapshot; rebuilding is manual and there is no live
monitoring.
- There is no auth, roles, or retention policy. That is acceptable for a local
read-only prototype, not for internal data.
- The checker is rule-based. It catches invented quotes, unknown evidence IDs,
trend language under insufficient evidence, and rename errors, but not every
plausible bad sentence. Candidate and inferential output still needs review.
- Taxonomy mappings are judgement calls. Confidence and secondary matches are
shown so a reviewer can see how strong the bridge is.


## Next up

- Live collectors is the most obvious, finding a way to get over the terms & conditions to source this data instead of getting it manually. 
- Auth/roles/retention since this is only local and read-only.
- Public APIs for social pricing to be collected automatically.
- Materialised metrics computed once instead of rebuilding everytime.
- Model/prompt versioning to use the best models according to different task, for example oumi decision model would be a good fit here.
