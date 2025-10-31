"""Tests for Snowflake CLI wrapper."""

import os
from unittest.mock import patch

import pytest

from igloo_mcp.config import Config, SnowflakeConfig
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


@patch("igloo_mcp.snow_cli.shutil.which", return_value=None)
def test_run_query_requires_cli(mock_which):
    cli = SnowCLI(profile="default")
    with pytest.raises(SnowCLIError):
        cli.run_query("SELECT 1")
    mock_which.assert_called_once()


@patch("igloo_mcp.snow_cli.shutil.which", return_value="/usr/bin/snow")
@patch("igloo_mcp.snow_cli.subprocess.run")
def test_run_file_success(mock_run, _):
    mock_run.return_value = type(
        "CP",
        (),
        {"stdout": "", "stderr": "", "returncode": 0},
    )()

    cli = SnowCLI(profile="default")
    out = cli.run_file("script.sql", output_format="json")
    assert out.returncode == 0


@patch("igloo_mcp.snow_cli.shutil.which", return_value="/usr/bin/snow")
@patch("igloo_mcp.snow_cli.subprocess.run")
def test_run_file_failure(mock_run, _):
    mock_run.return_value = type(
        "CP",
        (),
        {"stdout": "", "stderr": "boom", "returncode": 1},
    )()

    cli = SnowCLI(profile="default")
    with pytest.raises(SnowCLIError):
        cli.run_file("script.sql")


@patch("igloo_mcp.snow_cli.shutil.which", return_value="/usr/bin/snow")
@patch("igloo_mcp.snow_cli.subprocess.run")
def test_list_connections_parses_json(mock_run, _):
    mock_run.return_value = type(
        "CP",
        (),
        {"stdout": '[{"name": "dev"}]', "stderr": "", "returncode": 0},
    )()
    cli = SnowCLI(profile="default")
    assert cli.list_connections() == [{"name": "dev"}]


@patch("igloo_mcp.snow_cli.shutil.which", return_value="/usr/bin/snow")
@patch("igloo_mcp.snow_cli.subprocess.run")
def test_list_connections_failure(mock_run, _):
    mock_run.return_value = type(
        "CP",
        (),
        {"stdout": "", "stderr": "nope", "returncode": 1},
    )()
    cli = SnowCLI(profile="default")
    with pytest.raises(SnowCLIError):
        cli.list_connections()


@patch("igloo_mcp.snow_cli.SnowCLI.list_connections", return_value=[{"name": "dev"}])
def test_connection_exists_true(mock_list):
    cli = SnowCLI(profile="default")
    assert cli.connection_exists("dev") is True


@patch("igloo_mcp.snow_cli.SnowCLI.list_connections", side_effect=SnowCLIError("boom"))
def test_connection_exists_handles_error(mock_list):
    cli = SnowCLI(profile="default")
    assert cli.connection_exists("dev") is False


@patch("igloo_mcp.snow_cli.shutil.which", return_value="/usr/bin/snow")
@patch("igloo_mcp.snow_cli.subprocess.run")
def test_add_connection_success(mock_run, _):
    mock_run.return_value = type(
        "CP",
        (),
        {"stdout": "", "stderr": "", "returncode": 0},
    )()
    cli = SnowCLI(profile="default")
    cli.add_connection(
        "dev",
        account="acct",
        user="user",
        private_key_file="key.p8",
        role="role",
        make_default=True,
    )
    assert mock_run.called


@patch("igloo_mcp.snow_cli.shutil.which", return_value="/usr/bin/snow")
@patch("igloo_mcp.snow_cli.subprocess.run")
def test_add_connection_failure(mock_run, _):
    mock_run.return_value = type(
        "CP",
        (),
        {"stdout": "", "stderr": "bad", "returncode": 1},
    )()
    cli = SnowCLI(profile="default")
    with pytest.raises(SnowCLIError):
        cli.add_connection(
            "dev",
            account="acct",
            user="user",
            private_key_file="key.p8",
        )


@patch("igloo_mcp.snow_cli.shutil.which", return_value="/usr/bin/snow")
@patch("igloo_mcp.snow_cli.subprocess.run")
def test_set_default_connection_failure(mock_run, _):
    mock_run.return_value = type(
        "CP",
        (),
        {"stdout": "", "stderr": "fail", "returncode": 1},
    )()
    cli = SnowCLI(profile="default")
    with pytest.raises(SnowCLIError):
        cli.set_default_connection("dev")


@patch("igloo_mcp.snow_cli.SnowCLI.run_query", side_effect=SnowCLIError("oops"))
def test_test_connection_handles_failure(mock_run):
    cli = SnowCLI(profile="default")
    assert cli.test_connection() is False


def test_base_args_applies_overrides():
    empty_config = SnowflakeConfig(
        profile="default",
        warehouse=None,
        database=None,
        schema=None,
        role=None,
    )
    with (
        patch.dict(os.environ, {}, clear=True),
        patch(
            "igloo_mcp.snow_cli.get_config",
            return_value=Config(snowflake=empty_config),
        ),
    ):
        cli = SnowCLI(profile="default")
        args = cli._base_args({"warehouse": "X", "role": "R", "schema": None})
    assert args[args.index("--warehouse") + 1] == "X"
    assert args[args.index("--role") + 1] == "R"


@patch("igloo_mcp.snow_cli.shutil.which", return_value="/usr/bin/snow")
@patch("igloo_mcp.snow_cli.subprocess.run")
@patch("igloo_mcp.snow_cli.print")
def test_run_query_debug_logging_handles_errors(mock_print, mock_run, _):
    os.environ["IGLOO_MCP_DEBUG"] = "1"
    mock_print.side_effect = RuntimeError("no tty")
    mock_run.return_value = type(
        "CP",
        (),
        {"stdout": '[{"a":1}]', "stderr": "", "returncode": 0},
    )()
    cli = SnowCLI(profile="default")
    cli.run_query("SELECT 1", output_format="json")
    os.environ.pop("IGLOO_MCP_DEBUG", None)


@patch("igloo_mcp.snow_cli.shutil.which", return_value="/usr/bin/snow")
@patch("igloo_mcp.snow_cli.subprocess.run")
def test_run_query_json_dict_parsing(mock_run, _):
    mock_run.return_value = type(
        "CP",
        (),
        {"stdout": '{"data": [{"id": 1}] }', "stderr": "", "returncode": 0},
    )()
    cli = SnowCLI(profile="default")
    out = cli.run_query("SELECT 1", output_format="json")
    assert out.rows == [{"id": 1}]
    assert out.columns == ["id"]


@patch("igloo_mcp.snow_cli.shutil.which", return_value="/usr/bin/snow")
@patch("igloo_mcp.snow_cli.subprocess.run")
def test_run_query_json_decode_failure(mock_run, _):
    mock_run.return_value = type(
        "CP",
        (),
        {"stdout": "<html>nope</html>", "stderr": "", "returncode": 0},
    )()
    cli = SnowCLI(profile="default")
    out = cli.run_query("SELECT 1", output_format="json")
    assert out.rows is None


@patch("igloo_mcp.snow_cli.shutil.which", return_value="/usr/bin/snow")
@patch("igloo_mcp.snow_cli.subprocess.run")
@patch("igloo_mcp.snow_cli.print")
def test_run_file_debug_logging(mock_print, mock_run, _):
    os.environ["IGLOO_MCP_DEBUG"] = "1"
    mock_print.side_effect = RuntimeError("oops")
    mock_run.return_value = type(
        "CP",
        (),
        {"stdout": "", "stderr": "", "returncode": 0},
    )()
    cli = SnowCLI(profile="default")
    cli.run_file("script.sql", output_format="csv")
    os.environ.pop("IGLOO_MCP_DEBUG", None)


@patch("igloo_mcp.snow_cli.SnowCLI.run_query")
def test_test_connection_uses_stdout_when_no_rows(mock_run_query):
    mock_run_query.return_value = QueryOutput(
        raw_stdout=" 1 ", raw_stderr="", returncode=0, rows=None
    )
    cli = SnowCLI(profile="default")
    assert cli.test_connection() is True


@patch("igloo_mcp.snow_cli.shutil.which", return_value="/usr/bin/snow")
@patch("igloo_mcp.snow_cli.subprocess.run")
def test_list_connections_decode_failure(mock_run, _):
    mock_run.return_value = type(
        "CP",
        (),
        {"stdout": "not json", "stderr": "", "returncode": 0},
    )()
    cli = SnowCLI(profile="default")
    assert cli.list_connections() == []


@patch("igloo_mcp.snow_cli.shutil.which", return_value="/usr/bin/snow")
@patch("igloo_mcp.snow_cli.subprocess.run")
def test_add_connection_includes_optional_args(mock_run, _):
    mock_run.return_value = type(
        "CP", (), {"stdout": "", "stderr": "", "returncode": 0}
    )()
    cli = SnowCLI(profile="default")
    cli.add_connection(
        "dev",
        account="acct",
        user="user",
        private_key_file="key",
        role="role",
        warehouse="wh",
        database="db",
        schema="sc",
        make_default=True,
    )
    args = mock_run.call_args[0][0]
    assert "--warehouse" in args and "wh" in args
    assert "--database" in args and "db" in args
    assert "--schema" in args and "sc" in args
    assert "--default" in args


@patch("igloo_mcp.snow_cli.shutil.which", return_value="/usr/bin/snow")
@patch("igloo_mcp.snow_cli.subprocess.run")
def test_set_default_connection_success(mock_run, _):
    mock_run.return_value = type(
        "CP", (), {"stdout": "", "stderr": "", "returncode": 0}
    )()
    cli = SnowCLI(profile="default")
    cli.set_default_connection("dev")
    mock_run.assert_called_once()


def test_context_manager_returns_self():
    cli = SnowCLI(profile="default")
    with cli as entered:
        assert entered is cli
