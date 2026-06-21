from dcindex.parsers.mysqldump import parse_dump


def test_parses_tables_and_positional_columns(dump_sql):
    tables = parse_dump(dump_sql)
    assert {"events", "speakers", "demolabs", "villages", "pages", "vendors"} <= set(tables)

    events = tables["events"]
    # column order recovered from CREATE TABLE (INSERTs carry no column list)
    assert events.columns[:5] == ["day", "hour", "starttime", "endtime", "continuation"]
    assert len(events.rows) == 3  # H1, H1-continuation, H2
    first = events.rows[0]
    assert first["hash"] == "H1"
    assert first["title"] == "'Breaking Kernels'"  # literal wrapping quotes preserved by the parser
    assert first["modflag"] is None  # NULL -> None
    assert first["autoincre"] == 1  # numeric coercion


def test_handles_escapes_and_doubled_quotes():
    sql = (
        "CREATE TABLE `t` (`a` text, `b` int);\n"
        "INSERT INTO `t` VALUES ('line1\\nline2', 5),('it''s ok', 7);"
    )
    rows = parse_dump(sql)["t"].rows
    assert rows[0]["a"] == "line1\nline2"  # \n decoded
    assert rows[0]["b"] == 5
    assert rows[1]["a"] == "it's ok"  # doubled '' -> single '


def test_explicit_column_list_is_respected():
    sql = "INSERT INTO `x` (`name`,`n`) VALUES ('alpha', 1),('beta', 2);"
    rows = parse_dump(sql)["x"].rows
    assert rows == [{"name": "alpha", "n": 1}, {"name": "beta", "n": 2}]


def test_embedded_commas_and_parens_in_strings_do_not_break_parsing():
    sql = "CREATE TABLE `t` (`a` text);\nINSERT INTO `t` VALUES ('a, (b), c'),('plain');"
    rows = parse_dump(sql)["t"].rows
    assert rows[0]["a"] == "a, (b), c"
    assert rows[1]["a"] == "plain"
