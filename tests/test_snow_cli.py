"""Tests for Snowflake CLI wrapper."""

from unittest.mock import patch

import pytest

from igloo_mcp.snow_cli import QueryOutput, SnowCLI, SnowCLIError


@patch("igloo_mcp.snow_cli.shutil.which", return_value="/usr/bin/snow")
@patch("igloo_mcp.snow_cli.subprocess.run")
def test_run_query_csv_parsing(mock_run, _):
    mock_run.return_value = type(
        "CP",
        (),
        {
            "stdout": "col1,col2\n1,a\n2,b\n",
            "stderr": "",
            "returncode": 0,
        },
    )()

    cli = SnowCLI(profile="default")
    out = cli.run_query("SELECT 1", output_format="csv")
    assert out.rows is not None
    assert len(out.rows) == 2
    assert out.rows[0]["col1"] == "1"


@patch("igloo_mcp.snow_cli.shutil.which", return_value="/usr/bin/snow")
@patch("igloo_mcp.snow_cli.subprocess.run")
def test_run_query_json_parsing(mock_run, _):
    mock_run.return_value = type(
        "CP",
        (),
        {"stdout": '[{"a":1}]', "stderr": "", "returncode": 0},
    )()

    cli = SnowCLI(profile="default")
    out = cli.run_query("SELECT 1", output_format="json")
    assert out.rows is not None
    assert isinstance(out.rows, list)


@patch("igloo_mcp.snow_cli.shutil.which", return_value="/usr/bin/snow")
@patch("igloo_mcp.snow_cli.subprocess.run")
def test_run_query_error_raises(mock_run, _):
    mock_run.return_value = type(
        "CP",
        (),
        {"stdout": "", "stderr": "boom", "returncode": 1},
    )()

    cli = SnowCLI(profile="default")
    with pytest.raises(SnowCLIError):
        cli.run_query("SELECT 1")


@patch("igloo_mcp.snow_cli.SnowCLI.run_query")
def test_test_connection_success(mock_run_query):
    mock_run_query.return_value = QueryOutput(
        raw_stdout="1\n", raw_stderr="", returncode=0, rows=[{"1": "1"}]
    )
    cli = SnowCLI(profile="default")
    assert cli.test_connection() is True
