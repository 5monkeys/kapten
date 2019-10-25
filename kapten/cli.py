import argparse
import logging
import sys

from . import __version__
from .exceptions import KaptenError
from .log import logger
from .tool import Kapten


def command(input_args=None):
    if input_args is None:
        input_args = sys.argv[1:]

    parser = argparse.ArgumentParser(
        description="Checks for new images and updates services if needed."
    )
    parser.add_argument(
        "--version",
        dest="show_version",
        action="store_true",
        help="Show version and exit.",
    )
    parser.add_argument(
        "-s",
        "--service",
        type=str,
        action="append",
        dest="services",
        help="Service to update.",
    )
    parser.add_argument("-p", "--project", type=str, help="Optional project name.")
    parser.add_argument(
        "--server", action="store_true", help="Run kapten in server mode."
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Kapten server host. [default: 0.0.0.0]",
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Kapten server port. [default: 8000]"
    )
    parser.add_argument(
        "--slack-token", type=str, help="Slack token to use for notification."
    )
    parser.add_argument(
        "--slack-channel",
        type=str,
        help="Optional Slack channel to use for notification.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only check if service needs to be updated.",
    )
    parser.add_argument("--force", action="store_true", help="Force service update.")
    parser.add_argument(
        "-v",
        "--verbosity",
        type=int,
        default=1,
        help="Level of verbosity. [default: 1]",
    )

    args = parser.parse_args(input_args)

    # Show version
    if args.show_version:
        print("Kapten {}".format(__version__))
        exit(0)

    # Validate required args
    if not args.services:
        parser.error("Missing required argument SERVICES")

    # Set verbosity
    level = logging.INFO
    if args.verbosity == 0:
        level = logging.CRITICAL
    elif args.verbosity > 1:
        level = logging.DEBUG

    logger.setLevel(level)

    # Configure
    captain = Kapten(
        args.services,
        project=args.project,
        slack_token=args.slack_token,
        slack_channel=args.slack_channel,
        only_check=args.check,
        force=args.force,
    )

    if args.server:
        # Start server
        try:
            from kapten import server
        except ImportError:
            parser.error(
                "Unable to start server, ensure starlette and uvicorn is installed"
            )
        else:
            server.run(captain, host=args.host, port=args.port)

    else:
        # Run one-off check/update
        try:
            captain.update_services()
        except KaptenError as e:
            logger.critical(str(e))
            exit(666)
