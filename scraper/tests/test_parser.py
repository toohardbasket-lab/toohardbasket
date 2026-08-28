"""Tests for thb_parser against real fixtures harvested from aph.gov.au on 23 Aug 2026."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import date
from thb_parser import (parse_classic_text, parse_statsnet_text,
                        parse_long_date, parse_slash_date, split_inquiry_committee)

FIX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures")


def load(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return f.read()


def test_date_parsing():
    assert parse_long_date("Report tabled 23 August 2010") == date(2010, 8, 23)
    assert parse_long_date("Report tbled 17 November 2010") == date(2010, 11, 17)  # APH typo
    assert parse_slash_date("Response tabled: 1/4/2026") == date(2026, 4, 1)
    assert parse_long_date("no date here") is None


def test_committee_split():
    q, c = split_inquiry_committee(
        "A certain maritime incident Select Committee for an inquiry into a certain maritime incident")
    assert q == "A certain maritime incident"
    assert c.startswith("Select Committee for")
    q, c = split_inquiry_committee(
        "Gene patents review Community Affairs References Committee")
    assert c == "Community Affairs References Committee"


def test_classic_2011():
    rows = parse_classic_text(load("classic_2011.txt"), "classic/2011")
    # The page header states 67 tabled/presented in 2011 + 3 presented 2010 = 70
    assert len(rows) == 70, f"expected 70 rows, got {len(rows)}"
    # Known extreme: Civics and electoral education, JSCEM, 2007 -> 2011
    civics = [r for r in rows if "Civics and electoral" in r.inquiry][0]
    assert civics.report_last_tabled == "2007-06-18"
    assert civics.response_tabled == "2011-09-12"
    assert civics.days_to_respond == 1547
    assert civics.interim_only is False  # final response supersedes 2008 interim
    # Standalone entry with no title (committee name is the inquiry)
    md = [r for r in rows if r.committee.startswith("Ministerial Discretion")][0]
    assert md.report_last_tabled == "2004-03-31"
    assert md.response_tabled == "2011-07-04"
    # Every row must have committee + both dates or a note explaining why not
    for r in rows:
        assert r.committee
        assert (r.report_last_tabled and r.response_tabled) or r.notes, r.raw


def test_classic_2005():
    rows = parse_classic_text(load("classic_2005.txt"), "classic/2005")
    assert len(rows) == 40, f"expected 40 rows, got {len(rows)}"
    nursing = [r for r in rows if "Nursing: The patient profession" in r.inquiry][0]
    assert nursing.report_last_tabled == "2002-06-26"
    assert nursing.days_to_respond == 1233


def test_statsnet_2026():
    rows = parse_statsnet_text(load("statsnet_2026.txt"), "statsnet/2026")
    assert len(rows) >= 175, f"expected ~181 rows, got {len(rows)}"
    mi = [r for r in rows if r.inquiry == "A certain maritime incident"][0]
    assert mi.report_last_tabled == "2002-10-23"
    assert mi.response_tabled == "2026-04-01"
    assert mi.days_to_respond == 8561
    # multi-report inquiry: conservative clock from LAST report tabled
    sg = [r for r in rows if r.inquiry == "Administration of Sports Grants"][0]
    assert sg.report_first_tabled == "2020-12-01"
    assert sg.report_last_tabled == "2021-03-18"
    assert sg.response_tabled == "2026-06-22"
    # committee split coverage: at least 95% of rows split cleanly
    unsplit = [r for r in rows if not r.committee]
    assert len(unsplit) / len(rows) < 0.05, [r.inquiry[:60] for r in unsplit]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"PASS {name}")
    print("all tests passed")
