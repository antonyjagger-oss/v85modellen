# Stats Section Notes

Keep the landing page lean. Build a separate stats section/page for deeper transparency and utility.

## Good Candidates

- Rolling 7-day and 30-day union summary
- Wins, fulltraffar, near misses
- Payout distribution by game type
- Breakdown by game type: `V75`, `V86`, `V64`, `V65`, `V5`, `V4`, `V3`, `DD`
- Breakdown by track
- Latest winning coupons
- Latest near misses
- Signal contribution summaries:
  - `formlines`
  - `v5`
  - `tc`
  - `odds`
- Refresh timestamp and data coverage window
- Archive view of recent settled union runs

## Keep Off The Front Page

- Raw cumulative cost
- Blunt negative ROI framing
- Long loss streak framing
- Internal/debug metrics without user context

## Possible UX Split

- Front page:
  - recent results
  - near misses
  - recent union coupons
  - selected payouts
- Stats page:
  - full rollups
  - filters by game type / track / date window
  - transparency/audit views

## Implementation Direction

- Generate stats from `/home/dodge/v75/race_database.db`
- Extend `scripts/build_feed.py` or add a second exporter for stats-specific JSON
- Keep public payloads curated, not raw table dumps
