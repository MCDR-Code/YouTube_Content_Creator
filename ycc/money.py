"""Business numbers, all calculated in code: Partner Program progress, income estimate, costs, profit."""
from __future__ import annotations

import datetime as dt

# YouTube Partner Program bar for ad revenue. New applicants need the higher bar from Feb 1, 2027.
YPP_CHANGE_DATE = dt.date(2027, 2, 1)
YPP_NOW = {"subscribers": 1000, "watch_hours_12mo": 4000, "shorts_views_90d": 10_000_000}
YPP_2027 = {"subscribers": 1000, "watch_hours_12mo": 8000, "shorts_views_90d": 20_000_000}

# Simple, clearly labeled assumptions for the affiliate estimate (no ads until the channel qualifies).
AFFILIATE_CLICK_RATE = 0.004      # clicks per view on description links
AFFILIATE_CONVERSION = 0.03       # purchases per click
AFFILIATE_COMMISSION_USD = 2.00   # average commission per purchase


def partner_program(state: dict, today: dt.date | None = None) -> dict:
    today = today or dt.date.today()
    bar = YPP_2027 if today >= YPP_CHANGE_DATE else YPP_NOW
    subs_pct = min(100.0, 100 * state["subscribers"] / bar["subscribers"])
    hours_pct = min(100.0, 100 * state["watch_hours_12mo"] / bar["watch_hours_12mo"])
    shorts_pct = min(100.0, 100 * state["shorts_views_90d"] / bar["shorts_views_90d"])
    best_route = "watch hours" if hours_pct >= shorts_pct else "Shorts views"
    return {
        "bar": bar,
        "bar_note": "Higher bar for new applicants from Feb 1, 2027" if bar is YPP_2027 else
                    "Current bar; new applicants need 8,000 hours or 20M Shorts views from Feb 1, 2027",
        "subscribers": state["subscribers"], "subscribers_pct": round(subs_pct, 1),
        "watch_hours_12mo": state["watch_hours_12mo"], "watch_hours_pct": round(hours_pct, 2),
        "shorts_views_90d": state["shorts_views_90d"], "shorts_views_pct": round(shorts_pct, 3),
        "closest_route": best_route,
        "qualified": subs_pct >= 100 and max(hours_pct, shorts_pct) >= 100,
    }


def weekly_money(stats: dict, prune_cost_by_agent: dict[str, float], other_costs_usd: float = 0.0,
                 state: dict | None = None) -> dict:
    ypp = partner_program(state) if state else None
    ad_revenue = 0.0  # no ad revenue until the channel joins the Partner Program
    affiliate = round(stats["views"] * AFFILIATE_CLICK_RATE * AFFILIATE_CONVERSION * AFFILIATE_COMMISSION_USD, 2)
    prune_total = round(sum(prune_cost_by_agent.values()), 4)
    income = round(ad_revenue + affiliate, 2)
    return {
        "estimated": True,
        "income_usd": {"ads": ad_revenue, "affiliate_estimate": affiliate, "sponsors": 0.0, "total": income},
        "costs_usd": {"prune_by_agent": prune_cost_by_agent, "prune_total": prune_total, "other": other_costs_usd,
                      "total": round(prune_total + other_costs_usd, 4)},
        "profit_usd": round(income - prune_total - other_costs_usd, 2),
        "assumptions": {"affiliate_click_rate": AFFILIATE_CLICK_RATE, "affiliate_conversion": AFFILIATE_CONVERSION,
                        "affiliate_commission_usd": AFFILIATE_COMMISSION_USD},
        "partner_program": ypp,
    }


def per_video(stats: dict, uploads: list[dict], cost_by_video: dict[str, float]) -> list[dict]:
    """Views, estimated income, cost and profit per uploaded video (all estimates, code only)."""
    shorts = [u for u in uploads if u["kind"] == "short"]
    rows = []
    for u in uploads:
        views = stats["long_video_views"] if u["kind"] == "long" else (
            stats["shorts_views"] // max(1, len(shorts)))
        income = round(views * AFFILIATE_CLICK_RATE * AFFILIATE_CONVERSION * AFFILIATE_COMMISSION_USD, 2)
        cost = round(cost_by_video.get(u["id"], 0.0), 6)
        rows.append({"id": u["id"], "kind": u["kind"], "title": u["title"], "views": views,
                     "income_usd": income, "cost_usd": cost, "profit_usd": round(income - cost, 4)})
    return rows
