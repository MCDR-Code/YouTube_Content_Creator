import datetime as dt

import pytest

from ycc import money, schemas
from ycc.agents import BadAgentOutput, check, parse_json, wrap_input


def test_fail_verdict_needs_issues():
    with pytest.raises(Exception):
        schemas.FactCheck(verdict="FAIL", issues=[])


def test_parse_json_tolerates_code_fences():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('Here you go: {"a": 2} thanks') == {"a": 2}


def test_wrong_shape_is_caught():
    with pytest.raises(BadAgentOutput):
        check('{"topics": []}', schemas.TrendReport, "Trend Scout")


def test_comments_are_wrapped_and_links_removed():
    text = wrap_input({"x": 1}, ["see http://spam.example now"])
    assert "<comments>" in text and "spam.example" not in text


def test_partner_program_bar_doubles_feb_2027():
    state = {"subscribers": 500, "watch_hours_12mo": 2000.0, "shorts_views_90d": 0}
    before = money.partner_program(state, dt.date(2027, 1, 31))
    after = money.partner_program(state, dt.date(2027, 2, 1))
    assert before["bar"]["watch_hours_12mo"] == 4000 and before["watch_hours_pct"] == 50.0
    assert after["bar"]["watch_hours_12mo"] == 8000 and after["watch_hours_pct"] == 25.0


def test_profit_is_income_minus_costs():
    m = money.weekly_money({"views": 10000}, {"scriptwriter": 0.5, "director": 0.25}, other_costs_usd=1.0)
    assert m["income_usd"]["ads"] == 0.0
    assert m["income_usd"]["affiliate_estimate"] == round(10000 * 0.004 * 0.03 * 2.0, 2)
    assert m["profit_usd"] == round(m["income_usd"]["total"] - 0.75 - 1.0, 2)
