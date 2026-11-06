"""CLI for pinned engine reads.

Examples
--------
Fixture replay, no credentials:

    python3 -m engine_read --cutoff 2026-11-06T07:50:00+08:00 \\
        --output-dir /tmp/engine-read --fixture /tmp/fixture.json

Parent routine, public commit metadata plus connector file assets:

    python3 -m engine_read --cutoff 2026-11-06T19:50:00+08:00 \\
        --output-dir /tmp/engine-read \\
        --commits-transport api --contents-transport handoff --handoff -
"""

from __future__ import annotations

import argparse
import sys

from engine_read.transport import GithubHttpTransport
from engine_read.run import config_from_args, execute, fixture_transport, load_handoff, write_outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="engine_read", description="Pin and read the three China engine repos.")
    parser.add_argument("--cutoff", help="ISO instant. Naive values are Asia/Shanghai.")
    parser.add_argument("--as-of", help="Alias of --cutoff.")
    parser.add_argument("--output-dir", required=True, help="Temp or work directory outside this archive repo.")
    parser.add_argument("--edition", choices=("morning", "evening", "weekend"))
    parser.add_argument("--ref", default="main", help="Ref used only to resolve the cutoff commit.")
    parser.add_argument("--fixture", help="JSON map of cached responses. Sets fixture_mode and does not use the network.")
    parser.add_argument("--handoff", help="Connector manifest path, or - for stdin.")
    parser.add_argument("--commits-transport", choices=("api", "handoff"), default="api")
    parser.add_argument("--contents-transport", choices=("api", "handoff"), default="api")
    parser.add_argument("--prefer", choices=("auto", "contents", "blob", "raw"), default="auto")
    parser.add_argument("--max-bytes", type=int, help="Honest body ceiling. Shorter bodies are truncated, not parsed as complete JSON.")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--fetched-at", help="Override receipt clock. Naive values are Asia/Shanghai.")
    parser.add_argument(
        "--allow-env-auth",
        action="store_true",
        help="Attach GITHUB_TOKEN or GH_TOKEN if one is already in the environment. Default is unauthenticated. Does not read gh config.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.contents_transport == "handoff" and not args.handoff and not args.fixture:
        parser.error("--contents-transport handoff requires --handoff")
    if args.commits_transport == "handoff" and not args.handoff and not args.fixture:
        parser.error("--commits-transport handoff requires --handoff")
    handoff = load_handoff(args.handoff) if args.handoff else None
    try:
        config = config_from_args(args, handoff)
    except ValueError as exc:
        parser.error(str(exc))
    if args.fixture:
        transport = fixture_transport(args.fixture)
    else:
        transport = GithubHttpTransport(use_env_auth=args.allow_env_auth)
    result = execute(config, transport)
    write_outputs(config.output_dir, result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
