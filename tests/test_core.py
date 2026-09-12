from decimal import Decimal
from ustracker.money import parse_money_api, parse_money_ptbr, split_cents, due_date


def test_money_parsing_and_split_are_exact():
    assert parse_money_api('10.25') == 1025
    assert parse_money_ptbr('1.234,56') == 123456
    assert split_cents(100, [1, 1, 1]) == [34, 33, 33]


def test_due_date_clamps_month_end():
    assert due_date('2026-02', 31).isoformat() == '2026-02-28'
    assert due_date('2028-02', 31).isoformat() == '2028-02-29'
