# Turf Intelligence Known Issues

This file is for active handoff-month known issues and known limits.

The goal is to keep this short and honest. If an item stops being true, remove it.

## Current status

No critical known handoff blockers are open right now.

## Active handoff-month issues

- No active handoff-blocking issues are open right now.

## Final handoff known-issues list

- No critical handoff blockers are currently open.
- The main remaining issues are deeper product-depth and deployment-model limits, not stability failures.

## Known limits

- Only `static/product-labels` is intentionally public. Other local third-party document buckets remain private/internal by policy.
- Some product names are still known by the app without being fully structured in the verified KB, but that list is smaller again now. In those cases, the intended behavior is to answer with `Not Verified Yet` rather than guessing.
- The deterministic label layer is strong, and the silent-field gaps are much smaller now, but not every lower-traffic product has the same depth as the most common products.
- Broad agronomy and scouting answers are stronger and more operator-shaped now, but they are still expandable in tone and property-specific depth.
- The current supported launch model remains a managed/single-instance shape unless the remaining deeper admin/training persistence is fully replatformed.

## If a new issue is found

Add:

- the user-facing symptom
- whether it is a real bug or a known limit
- the smallest safe next step

Do not turn this file into a backlog dump.
