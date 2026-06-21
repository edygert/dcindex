import pytest

from dcindex.core.editions import (
    dump_url_for,
    edition_from_path,
    from_year,
    parse_edition,
)


@pytest.mark.parametrize(
    "token,number,year",
    [
        ("dc30", 30, 2022),
        ("DC30", 30, 2022),
        ("defcon30", 30, 2022),
        ("defcon-30", 30, 2022),
        ("def con 30", 30, 2022),
        ("30", 30, 2022),
        ("2022", 30, 2022),
        ("dc26", 26, 2018),
        ("dc33", 33, 2025),
    ],
)
def test_parse_edition(token, number, year):
    ed = parse_edition(token)
    assert ed is not None
    assert ed.number == number
    assert ed.year == year
    assert ed.slug == f"defcon-{number}"
    assert ed.name == f"DEF CON {number}"


def test_parse_edition_none():
    assert parse_edition("") is None
    assert parse_edition("not-an-edition") is None


def test_from_year_bounds():
    assert from_year(2018).number == 26
    assert from_year(1900) is None  # before DEF CON 1


def test_edition_from_path():
    ed = edition_from_path("https://defcon.outel.org/defcon30/dc30_mysqldump.txt")
    assert ed is not None and ed.number == 30
    assert edition_from_path("/tmp/dc33_mysqldump.txt").number == 33
    assert edition_from_path("/tmp/random.sql") is None


def test_dump_url_for():
    ed = parse_edition("dc33")
    assert dump_url_for(ed) == "https://defcon.outel.org/defcon33/dc33_mysqldump.txt"
