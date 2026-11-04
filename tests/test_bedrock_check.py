"""CLI behaviour tests. These do not call AWS."""

from __future__ import annotations

from shambashield.bedrock_check import (
    EXIT_USAGE,
    _settings_from_args,
    build_parser,
    main,
    smoke_test,
)
from shambashield.config import Settings


def test_parser_reads_smoke_options() -> None:
    args = build_parser().parse_args(["--smoke", "--model", "test-model", "--verbose"])
    assert args.smoke is True
    assert args.model == "test-model"
    assert args.verbose is True


def test_region_and_profile_overrides() -> None:
    args = build_parser().parse_args(["--identity", "--region", "eu-west-1", "--profile", "dev"])
    settings = _settings_from_args(args)
    assert settings.aws_region == "eu-west-1"
    assert settings.aws_profile == "dev"


def test_no_command_prints_help(capsys) -> None:
    assert main([]) == EXIT_USAGE
    assert "usage:" in capsys.readouterr().out.lower()


def test_smoke_without_model_is_a_usage_error(capsys) -> None:
    settings = Settings(_env_file=None, bedrock_model_id=None)
    assert smoke_test(settings, None) == EXIT_USAGE
    assert "BEDROCK_MODEL_ID" in capsys.readouterr().err
