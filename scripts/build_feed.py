#!/usr/bin/env python3
import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, "/home/dodge/v75")

from coupon_evaluator import evaluate_game_coupon


def normalize_game_type(raw_game_type: Optional[str]) -> str:
    if not raw_game_type:
        return "?"
    return str(raw_game_type).upper()


def parse_args():
    parser = argparse.ArgumentParser(description="Build public V85Modellen feed from SQLite DB.")
    parser.add_argument(
        "--db",
        default="/home/dodge/v75/race_database.db",
        help="Path to source SQLite database",
    )
    parser.add_argument(
        "--output",
        default="/home/dodge/workspace/v85modellen/public/data/feed.json",
        help="Where to write feed JSON",
    )
    parser.add_argument(
        "--price",
        type=int,
        default=49,
        help="Alpha monthly price in SEK",
    )
    return parser.parse_args()


def connect_db(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


def normalize_sources(raw_tier: Optional[str]) -> List[str]:
    if not raw_tier:
        return []
    lower = raw_tier.lower()
    sources = []
    if "form" in lower:
        sources.append("formlines")
    if "v5" in lower:
        sources.append("v5")
    if "tc" in lower:
        sources.append("tc")
    if "odds" in lower:
        sources.append("odds")
    return sources


def fetch_track_for_game(cur: sqlite3.Cursor, game_id: str) -> str:
    row = cur.execute(
        """
        SELECT COALESCE(NULLIF(r.resolved_venue_name, ''), t.name, 'Unknown') AS track_name
        FROM game_races gr
        JOIN races r ON r.id = gr.race_id
        LEFT JOIN tracks t ON t.track_id = r.track_id
        WHERE gr.game_id = ?
        ORDER BY gr.leg_number
        LIMIT 1
        """,
        (game_id,),
    ).fetchone()
    return row["track_name"] if row else "Unknown"


def fetch_leg_winners(cur: sqlite3.Cursor, game_id: str) -> Dict[int, Optional[int]]:
    rows = cur.execute(
        """
        SELECT gr.leg_number,
               (
                   SELECT s.number
                   FROM starts s
                   WHERE s.race_id = gr.race_id
                     AND COALESCE(s.place, s.finish_order) = 1
                   LIMIT 1
               ) AS winner_no
        FROM game_races gr
        WHERE gr.game_id = ?
        ORDER BY gr.leg_number
        """,
        (game_id,),
    ).fetchall()
    return {int(row["leg_number"]): row["winner_no"] for row in rows}


def fetch_coupon_legs(cur: sqlite3.Cursor, run_id: str) -> Dict[int, List[sqlite3.Row]]:
    rows = cur.execute(
        """
        SELECT leg, prog_no, horse_name, tier, ensemble_p1
        FROM coupon_selections
        WHERE run_id = ?
        ORDER BY leg, ensemble_p1 DESC, prog_no
        """,
        (run_id,),
    ).fetchall()
    grouped: Dict[int, List[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        grouped[int(row["leg"])].append(row)
    return grouped


def fetch_recent_completed_union_runs(cur: sqlite3.Cursor) -> List[sqlite3.Row]:
    return cur.execute(
        """
        WITH latest_union AS (
            SELECT meet_id, MAX(created_at) AS max_created
            FROM coupon_runs
            WHERE mode = 'union' AND is_frozen = 1
            GROUP BY meet_id
        )
        SELECT cr.run_id,
               cr.meet_id,
               cr.total_rows,
               cr.total_cost,
               cr.created_at,
               g.type AS game_type,
               g.status AS game_status,
               g.timestamp AS game_timestamp
        FROM latest_union lu
        JOIN coupon_runs cr
          ON cr.meet_id = lu.meet_id
         AND cr.created_at = lu.max_created
         AND cr.mode = 'union'
         AND cr.is_frozen = 1
        JOIN games g
          ON g.id = cr.meet_id
        WHERE g.status = 'results'
          AND DATE(COALESCE(g.timestamp, cr.created_at)) >= DATE('now', '-7 days')
        ORDER BY COALESCE(g.timestamp, cr.created_at) DESC
        """
    ).fetchall()


def fetch_completed_union_runs(cur: sqlite3.Cursor) -> List[sqlite3.Row]:
    return cur.execute(
        """
        WITH latest_union AS (
            SELECT meet_id, MAX(created_at) AS max_created
            FROM coupon_runs
            WHERE mode = 'union' AND is_frozen = 1
            GROUP BY meet_id
        )
        SELECT cr.run_id,
               cr.meet_id,
               cr.total_rows,
               cr.total_cost,
               cr.created_at,
               cr.frozen_at,
               g.type AS game_type,
               g.status AS game_status,
               g.timestamp AS game_timestamp
        FROM latest_union lu
        JOIN coupon_runs cr
          ON cr.meet_id = lu.meet_id
         AND cr.created_at = lu.max_created
         AND cr.mode = 'union'
         AND cr.is_frozen = 1
        JOIN games g
          ON g.id = cr.meet_id
        WHERE g.status = 'results'
        ORDER BY COALESCE(g.timestamp, cr.created_at) DESC
        """
    ).fetchall()


def fetch_latest_union_coupons(cur: sqlite3.Cursor, limit: int = 3) -> List[sqlite3.Row]:
    return cur.execute(
        """
        WITH latest_union AS (
            SELECT meet_id, MAX(created_at) AS max_created
            FROM coupon_runs
            WHERE mode = 'union' AND is_frozen = 1
            GROUP BY meet_id
        )
        SELECT cr.run_id,
               cr.meet_id,
               cr.total_rows,
               cr.total_cost,
               cr.created_at,
               g.type AS game_type,
               g.status AS game_status,
               g.timestamp AS game_timestamp
        FROM latest_union lu
        JOIN coupon_runs cr
          ON cr.meet_id = lu.meet_id
         AND cr.created_at = lu.max_created
         AND cr.mode = 'union'
         AND cr.is_frozen = 1
        LEFT JOIN games g
          ON g.id = cr.meet_id
        ORDER BY COALESCE(g.timestamp, cr.created_at) DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def build_recent_result(cur: sqlite3.Cursor, row: sqlite3.Row, db_path: str) -> Optional[dict]:
    winners = fetch_leg_winners(cur, row["meet_id"])
    if not winners:
        return None

    selections = fetch_coupon_legs(cur, row["run_id"])
    total_legs = len(winners)
    hits = 0
    leg_results = []

    for leg in sorted(winners):
        winner = winners[leg]
        picked = {int(sel["prog_no"]) for sel in selections.get(leg, [])}
        hit = winner is not None and winner in picked
        if hit:
            hits += 1
        leg_results.append("✓" if hit else "✗")

    payout_sek = None
    evaluation = evaluate_game_coupon(
        db_path,
        row["meet_id"],
        row["game_type"],
        mode="union",
    )
    if evaluation and evaluation.get("payout") is not None:
        payout_value = float(evaluation["payout"])
        if payout_value > 0:
            payout_sek = int(round(payout_value))

    status = f"{hits} rätt"
    if payout_sek:
        status += " — utdelning"

    date_str = str(row["meet_id"]).split("_")[1] if "_" in str(row["meet_id"]) else str(row["game_timestamp"])[:10]
    return {
        "date": date_str,
        "mode": "union",
        "game_id": row["meet_id"],
        "game_type": normalize_game_type(row["game_type"]),
        "track": fetch_track_for_game(cur, row["meet_id"]),
        "hits": hits,
        "total_legs": total_legs,
        "leg_results": leg_results,
        "payout_sek": payout_sek,
        "status": status,
        "cost_sek": int(round(float(row["total_cost"] or 0))),
    }


def build_wrap(cur: sqlite3.Cursor, row: sqlite3.Row, db_path: str) -> Optional[dict]:
    result = build_recent_result(cur, row, db_path)
    if not result:
        return None

    winners = fetch_leg_winners(cur, row["meet_id"])
    selections = fetch_coupon_legs(cur, row["run_id"])
    contributions = {"formlines": 0, "v5": 0, "tc": 0, "odds": 0}

    for leg, winner in winners.items():
        if winner is None:
            continue
        for sel in selections.get(leg, []):
            if int(sel["prog_no"]) == winner:
                for source in normalize_sources(sel["tier"]):
                    contributions[source] += 1
                break

    winning_contributions = {}
    for key, hits in contributions.items():
        if hits:
            winning_contributions[key] = {"hits": hits, "total": result["total_legs"]}

    payout_text = (
        f"Utdelning {result['payout_sek']:,} kr.".replace(",", " ")
        if result["payout_sek"]
        else "Ingen utdelning."
    )
    hit_legs = [str(i + 1) for i, mark in enumerate(result["leg_results"]) if mark == "✓"]
    miss_legs = [str(i + 1) for i, mark in enumerate(result["leg_results"]) if mark == "✗"]
    summary_bits = [f"{result['hits']} av {result['total_legs']} rätt.", payout_text]
    if hit_legs:
        summary_bits.append(f"Träff i avdelning {', '.join(hit_legs)}.")
    if miss_legs:
        summary_bits.append(f"Miss i avdelning {', '.join(miss_legs)}.")

    title = f"{result['game_type']} {result['track']} — {result['hits']}/{result['total_legs']} rätt"
    if result["payout_sek"]:
        title += f", {result['payout_sek']:,} kr".replace(",", " ")

    wrap = {
        "date": result["date"],
        "game_type": result["game_type"],
        "title": title,
        "summary": " ".join(summary_bits),
    }
    if winning_contributions:
        wrap["winning_contributions"] = winning_contributions
    return wrap


def build_coupon(cur: sqlite3.Cursor, row: sqlite3.Row) -> Optional[dict]:
    selections = fetch_coupon_legs(cur, row["run_id"])
    if not selections:
        return None

    legs = []
    for leg_no in sorted(selections):
        picks = []
        for sel in selections[leg_no]:
            sources = normalize_sources(sel["tier"])
            if not sources:
                sources = ["tc"]
            picks.append(
                {
                    "number": int(sel["prog_no"]),
                    "horse": sel["horse_name"] or f"Häst {sel['prog_no']}",
                    "source": sources,
                }
            )
        legs.append({"leg": leg_no, "picks": picks})

    return {
        "game_id": row["meet_id"],
        "game_type": normalize_game_type(row["game_type"] or row["meet_id"].split("_", 1)[0].upper()),
        "track": fetch_track_for_game(cur, row["meet_id"]),
        "mode": "union",
        "rows": int(row["total_rows"] or 0),
        "cost_sek": int(round(float(row["total_cost"] or 0))),
        "legs": legs,
    }


def build_performance_segment(results: List[dict], wraps: List[dict]) -> dict:
    if not results:
        return {
            "summary": {
                "settled_games": 0,
                "wins": 0,
                "near_misses": 0,
                "perfect_hits": 0,
                "total_cost_sek": 0,
                "total_payout_sek": 0,
                "roi_pct": 0.0,
            },
            "rolling": {"window_days": [7, 30], "series": []},
            "recent_results": [],
            "recent_wraps": [],
        }

    results_by_date: Dict[str, List[dict]] = defaultdict(list)
    for item in results:
        results_by_date[item["date"]].append(item)

    ordered_dates = sorted(results_by_date.keys())
    daily = []
    for date_str in ordered_dates:
        items = results_by_date[date_str]
        settled_games = len(items)
        wins = sum(1 for item in items if item.get("payout_sek"))
        near_misses = sum(
            1
            for item in items
            if item.get("hits", 0) == max(0, item.get("total_legs", 0) - 1)
        )
        perfect_hits = sum(
            1 for item in items if item.get("hits", 0) == item.get("total_legs", 0)
        )
        total_cost = sum(item.get("cost_sek", 0) or 0 for item in items)
        total_payout = sum(item.get("payout_sek", 0) or 0 for item in items)
        roi_pct = round(((total_payout - total_cost) / total_cost) * 100, 1) if total_cost else 0.0
        daily.append(
            {
                "date": date_str,
                "settled_games": settled_games,
                "wins": wins,
                "near_misses": near_misses,
                "perfect_hits": perfect_hits,
                "total_cost_sek": total_cost,
                "total_payout_sek": total_payout,
                "roi_pct": roi_pct,
            }
        )

    rolling_series = []
    for idx, point in enumerate(daily):
        row = {"date": point["date"]}
        for window in (7, 30):
            subset = daily[max(0, idx - window + 1): idx + 1]
            settled_games = sum(item["settled_games"] for item in subset)
            wins = sum(item["wins"] for item in subset)
            row[f"win_rate_{window}d"] = round((wins / settled_games) * 100, 1) if settled_games else 0.0
            total_cost = sum(item["total_cost_sek"] for item in subset)
            total_payout = sum(item["total_payout_sek"] for item in subset)
            row[f"roi_{window}d"] = round(((total_payout - total_cost) / total_cost) * 100, 1) if total_cost else 0.0
        rolling_series.append(row)

    total_cost = sum(item.get("cost_sek", 0) or 0 for item in results)
    total_payout = sum(item.get("payout_sek", 0) or 0 for item in results)
    summary = {
        "settled_games": len(results),
        "wins": sum(1 for item in results if item.get("payout_sek")),
        "near_misses": sum(
            1
            for item in results
            if item.get("hits", 0) == max(0, item.get("total_legs", 0) - 1)
        ),
        "perfect_hits": sum(
            1 for item in results if item.get("hits", 0) == item.get("total_legs", 0)
        ),
        "total_cost_sek": total_cost,
        "total_payout_sek": total_payout,
        "roi_pct": round(((total_payout - total_cost) / total_cost) * 100, 1) if total_cost else 0.0,
    }

    return {
        "summary": summary,
        "rolling": {
            "window_days": [7, 30],
            "series": rolling_series,
        },
        "recent_results": results[:30],
        "recent_wraps": wraps[:8],
    }


def build_performance(results: List[dict], wraps: List[dict], completed_rows: List[sqlite3.Row]) -> dict:
    union_started_on = None
    if completed_rows:
        raw_dates = []
        for row in completed_rows:
            raw_date = str(row["meet_id"]).split("_")[1] if "_" in str(row["meet_id"]) else None
            if raw_date:
                raw_dates.append(raw_date)
        if raw_dates:
            union_started_on = min(raw_dates)

    all_segment = build_performance_segment(results, wraps)

    segment_order = ["V85", "V86", "V75", "GS75", "V65", "V64", "V5", "V4", "V3", "DD"]
    available_types = sorted({item["game_type"] for item in results}, key=lambda gt: (segment_order.index(gt) if gt in segment_order else len(segment_order), gt))

    segments = {"all": all_segment}
    filters = [{"key": "all", "label": "Alla", "count": all_segment["summary"]["settled_games"]}]

    for game_type in available_types:
        type_results = [item for item in results if item["game_type"] == game_type]
        type_wraps = [wrap for wrap in wraps if wrap.get("game_type") == game_type]
        key = game_type.lower()
        segments[key] = build_performance_segment(type_results, type_wraps)
        filters.append({"key": key, "label": game_type, "count": len(type_results)})

    return {
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "union_started_on": union_started_on,
        "default_filter": "all",
        "filters": filters,
        "segments": segments,
        "summary": all_segment["summary"],
        "rolling": all_segment["rolling"],
        "recent_results": all_segment["recent_results"],
        "recent_wraps": all_segment["recent_wraps"],
    }


def build_feed(con: sqlite3.Connection, price: int, db_path: str) -> dict:
    cur = con.cursor()
    recent_run_rows = fetch_recent_completed_union_runs(cur)
    completed_union_rows = fetch_completed_union_runs(cur)
    coupon_rows = fetch_latest_union_coupons(cur, limit=3)

    recent_results = []
    wraps = []
    all_results = []
    all_wraps = []
    for row in completed_union_rows:
        item = build_recent_result(cur, row, db_path)
        if item:
            all_results.append(item)
        wrap = build_wrap(cur, row, db_path)
        if wrap:
            all_wraps.append(wrap)

    recent_game_ids = {row["meet_id"] for row in recent_run_rows}
    recent_results = [item for item in all_results if item["game_id"] in recent_game_ids]
    wraps = [wrap for wrap in all_wraps if wrap["date"] in {item["date"] for item in recent_results}]

    coupons = []
    for row in coupon_rows:
        coupon = build_coupon(cur, row)
        if coupon:
            coupons.append(coupon)

    total_cost = sum(item.get("cost_sek", 0) for item in recent_results)
    total_payout = sum(item.get("payout_sek", 0) or 0 for item in recent_results)
    settled = len(recent_results)
    wins = sum(1 for item in recent_results if item.get("payout_sek"))
    near_misses = sum(
        1
        for item in recent_results
        if item.get("hits", 0) == max(0, item.get("total_legs", 0) - 1)
    )
    perfect_hits = sum(
        1
        for item in recent_results
        if item.get("hits", 0) == item.get("total_legs", 0)
    )
    roi_pct = round(((total_payout - total_cost) / total_cost) * 100, 1) if total_cost else 0.0
    performance = build_performance(all_results, all_wraps, completed_union_rows)

    return {
        "brand": {
            "name": "V85Modellen",
            "tagline": "Union-kuponger och modellbaserad travanalys från de senaste 7 dagarnas riktiga körningar",
        },
        "links": {
            "patreon": "https://www.patreon.com/c/V85Modellen",
            "x": "https://x.com/v85Modellen",
        },
        "stats": {
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "alpha_price_sek_per_month": price,
            "rolling_window_days": 7,
            "union_games_settled": settled,
            "union_wins": wins,
            "union_near_misses": near_misses,
            "union_perfect_hits": perfect_hits,
            "union_total_cost_sek": total_cost,
            "union_total_payout_sek": total_payout,
            "union_roi_pct": roi_pct,
        },
        "recent_results": recent_results[:10],
        "wraps": wraps[:4],
        "sample_coupons": coupons,
        "performance": performance,
    }


def main():
    args = parse_args()
    con = connect_db(args.db)
    try:
        feed = build_feed(con, args.price, args.db)
    finally:
        con.close()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\n")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
