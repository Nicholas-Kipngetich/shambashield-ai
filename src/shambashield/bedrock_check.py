"""Bedrock connectivity diagnostics used in Phase 2 and later for smoke tests.

Commands::

    python scripts/check_bedrock.py --identity
    python scripts/check_bedrock.py --list
    python scripts/check_bedrock.py --smoke --model us.amazon.nova-lite-v1:0

The script never prints secret material. It only shows the caller ARN, the
region, model IDs and a short test response.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Sequence

from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    NoCredentialsError,
    ProfileNotFound,
)
from strands import Agent

from .aws import build_bedrock_model, get_boto_session
from .config import Settings
from .logging_setup import configure_logging, get_logger, new_request_id

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_AWS = 2
EXIT_MODEL = 3

log = get_logger(__name__)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _settings_from_args(args: argparse.Namespace) -> Settings:
    overrides: dict[str, str] = {}
    if args.region:
        overrides["aws_region"] = args.region
    if args.profile:
        overrides["aws_profile"] = args.profile
    return Settings(**overrides)


def _explain_aws_error(exc: Exception, settings: Settings) -> None:
    """Print an actionable message instead of a raw traceback."""
    region = settings.aws_region

    if isinstance(exc, NoCredentialsError):
        log.error(
            "No AWS credentials found. Configure a profile first, then set AWS_PROFILE in .env."
        )
        print(
            "\nFix:\n"
            "  1. Install the AWS CLI (one time):\n"
            "       winget install --id Amazon.AWSCLI -e\n"
            "  2. Configure SSO (recommended):\n"
            "       aws configure sso\n"
            "  3. Put the profile name in .env, e.g. AWS_PROFILE=shambashield\n"
            "  4. Re-run: python scripts/check_bedrock.py --identity\n",
            file=sys.stderr,
        )
        return

    if isinstance(exc, ProfileNotFound):
        log.error("AWS profile not found: %s", settings.aws_profile)
        print(
            "\nCheck `~/.aws/config` or run `aws configure sso`. "
            "Then update AWS_PROFILE in .env.\n",
            file=sys.stderr,
        )
        return

    if isinstance(exc, ClientError):
        error = exc.response.get("Error", {})
        code = error.get("Code", "Unknown")
        message = error.get("Message", str(exc))
        log.error("AWS error %s in %s: %s", code, region, message)

        if code in {"AccessDenied", "AccessDeniedException"}:
            print(
                "\nAccess denied.\n"
                "  * For --list: your principal needs bedrock:ListFoundationModels and\n"
                "    bedrock:ListInferenceProfiles.\n"
                "  * For --smoke: your principal needs bedrock:InvokeModel, and the model\n"
                "    must be enabled in the Bedrock console under 'Model access'.\n"
                f"  * Region in use: {region}\n",
                file=sys.stderr,
            )
        elif code in {"ValidationException", "ResourceNotFoundException"}:
            print(
                "\nThe model ID or inference profile was rejected.\n"
                f"  * Region: {region}\n"
                "  * List valid IDs: python scripts/check_bedrock.py --list\n"
                "  * Anthropic models often need a cross-region inference profile ID\n"
                "    beginning with 'us.' (or 'eu.'/'apac.' depending on region).\n",
                file=sys.stderr,
            )
        elif code in {"ThrottlingException", "TooManyRequestsException"}:
            print("\nBedrock throttled the request. Wait a moment and retry.\n", file=sys.stderr)
        elif code == "UnrecognizedClientException":
            print(
                "\nThe credentials were rejected. They may be expired or revoked.\n"
                "Re-authenticate (for SSO: `aws sso login --profile <name>`).\n",
                file=sys.stderr,
            )
        return

    if isinstance(exc, BotoCoreError):
        log.error("AWS SDK error: %s", exc)
        print(
            "\nCould not reach the AWS service.\n"
            "  * Check network access.\n"
            f"  * Confirm Bedrock is available in {region}.\n"
            "  * Try the recommended region: --region us-east-1\n",
            file=sys.stderr,
        )
        return

    log.error("Unexpected error: %s", exc)


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------
def check_identity(settings: Settings) -> int:
    print(f"Region: {settings.aws_region}")
    session = get_boto_session(settings)
    sts = session.client("sts")
    identity = sts.get_caller_identity()
    print("Credentials are valid.")
    print(f"  Account: {identity.get('Account')}")
    print(f"  ARN:     {identity.get('Arn')}")
    return EXIT_OK


def list_models(settings: Settings) -> int:
    session = get_boto_session(settings)
    bedrock = session.client("bedrock")
    region = settings.aws_region

    print(f"Region: {region}\n")
    print("Foundation models with text output and on-demand support")
    print("=" * 78)
    rows: list[tuple[str, str, str]] = []
    token: str | None = None
    while True:
        kwargs: dict = {"byOutputModality": "TEXT"}
        if token:
            kwargs["nextToken"] = token
        page = bedrock.list_foundation_models(**kwargs)
        for model in page.get("modelSummaries", []):
            inference_types = model.get("inferenceTypesSupported", [])
            if "ON_DEMAND" not in inference_types:
                continue
            rows.append(
                (
                    model.get("modelId", "?"),
                    model.get("providerName", "?"),
                    "streaming" if model.get("responseStreamingSupported") else "-",
                )
            )
        token = page.get("nextToken")
        if not token:
            break

    if not rows:
        print("No on-demand text models returned. Check model access and region.")
    else:
        for model_id, provider, streaming in sorted(rows):
            print(f"  {model_id:<62} {provider:<14} {streaming}")

    print("\nActive system inference profiles")
    print("=" * 78)
    profiles: list[tuple[str, str]] = []
    token = None
    while True:
        kwargs = {"typeEquals": "SYSTEM_DEFINED"}
        if token:
            kwargs["nextToken"] = token
        page = bedrock.list_inference_profiles(**kwargs)
        for profile in page.get("inferenceProfileSummaries", []):
            if profile.get("status") != "ACTIVE":
                continue
            profiles.append(
                (
                    profile.get("inferenceProfileId", "?"),
                    profile.get("inferenceProfileName", "?"),
                )
            )
        token = page.get("nextToken")
        if not token:
            break

    if not profiles:
        print("No active inference profiles returned.")
    else:
        for profile_id, name in sorted(profiles):
            print(f"  {profile_id:<62} {name}")

    print(
        "\nNext: copy a model or profile ID from above into .env as BEDROCK_MODEL_ID,\n"
        "then run: python scripts/check_bedrock.py --smoke\n"
    )
    return EXIT_OK


def smoke_test(settings: Settings, model_id: str | None) -> int:
    resolved = model_id or settings.bedrock_model_id
    if not resolved:
        log.error("No model ID supplied and BEDROCK_MODEL_ID is empty.")
        print(
            "\nRun `python scripts/check_bedrock.py --list`, choose an ID, then either:\n"
            "  * set BEDROCK_MODEL_ID in .env, or\n"
            "  * pass --model <id>\n",
            file=sys.stderr,
        )
        return EXIT_USAGE

    print(f"Region:      {settings.aws_region}")
    print(f"Model ID:    {resolved}")
    print("Sending one request through Strands...\n")

    model = build_bedrock_model(resolved, settings=settings, max_tokens=64)
    agent = Agent(
        model=model,
        system_prompt=(
            "You are a connectivity test for ShambaShield AI. "
            "Reply with exactly the sentence the user asks for, with no extra text."
        ),
        callback_handler=None,
    )

    started = time.perf_counter()
    result = agent("Reply with exactly: ShambaShield Bedrock connection OK")
    elapsed = time.perf_counter() - started
    text = str(result).strip()

    print("Response:")
    print(f"  {text}\n")
    print(f"Latency: {elapsed:.2f}s")

    if "ShambaShield Bedrock connection OK" not in text:
        log.warning("The model replied, but not with the exact requested sentence.")
        return EXIT_MODEL

    print("\nPhase 2 Bedrock smoke test passed.")
    return EXIT_OK


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check_bedrock",
        description="Verify AWS credentials, list Bedrock models, and run a Strands smoke test.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/check_bedrock.py --identity\n"
            "  python scripts/check_bedrock.py --list\n"
            "  python scripts/check_bedrock.py --smoke --model us.amazon.nova-lite-v1:0\n"
        ),
    )
    parser.add_argument("--identity", action="store_true", help="verify AWS credentials with STS")
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_models",
        help="list models/profiles",
    )
    parser.add_argument("--smoke", action="store_true", help="invoke a model through Strands")
    parser.add_argument("--model", help="model or inference profile ID for --smoke")
    parser.add_argument("--region", help="override AWS_REGION")
    parser.add_argument("--profile", help="override AWS_PROFILE")
    parser.add_argument("--verbose", action="store_true", help="enable debug logging")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not any([args.identity, args.list_models, args.smoke]):
        parser.print_help()
        return EXIT_USAGE

    settings = _settings_from_args(args)
    configure_logging("DEBUG" if args.verbose else settings.log_level)
    new_request_id()

    try:
        if args.identity:
            return check_identity(settings)
        if args.list_models:
            return list_models(settings)
        return smoke_test(settings, args.model)
    except (NoCredentialsError, ProfileNotFound, ClientError, BotoCoreError) as exc:
        _explain_aws_error(exc, settings)
        return EXIT_AWS
    except ValueError as exc:
        log.error("%s", exc)
        return EXIT_USAGE
    except Exception as exc:  # noqa: BLE001 - CLI boundary must be friendly
        log.error("Unexpected failure: %s", exc, exc_info=args.verbose)
        return EXIT_MODEL


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
