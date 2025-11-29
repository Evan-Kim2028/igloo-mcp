from igloo_mcp.sql_objects import extract_query_objects


def test_extract_query_objects_returns_unique_tables() -> None:
    sql = """
    SELECT *
    FROM CORE.PUBLIC.TRADES t
    JOIN ANALYTICS.MART.POSITIONS AS p
      ON t.position_id = p.id
    """

    objects = extract_query_objects(sql)

    names = {(obj.get("database"), obj.get("schema"), obj.get("name")) for obj in objects}

    assert ("CORE", "PUBLIC", "TRADES") in names
    assert ("ANALYTICS", "MART", "POSITIONS") in names
