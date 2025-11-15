from __future__ import annotations

import argparse

from igloo_mcp import report_cli


def test_build_arg_parser_has_subcommands() -> None:
    parser = report_cli.build_arg_parser()
    assert isinstance(parser, argparse.ArgumentParser)
    # Ensure the expected subcommands are registered
    subcommands = set()
    for action in parser._actions:  # type: ignore[attr-defined]
        if isinstance(action, argparse._SubParsersAction):  # type: ignore[attr-defined]
            subcommands.update(action.choices.keys())
    assert {"build", "lint", "scaffold"}.issubset(subcommands)
