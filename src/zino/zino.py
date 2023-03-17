#!/usr/bin/env python3
import argparse
import asyncio
import logging
from datetime import datetime

from zino.scheduler import get_scheduler, load_and_schedule_polldevs

_log = logging.getLogger("zino")


def main():
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s (%(threadName)s) - %(message)s"
    )
    init_event_loop(args)


def init_event_loop(args: argparse.Namespace):
    scheduler = get_scheduler()
    scheduler.start()

    scheduler.add_job(
        load_and_schedule_polldevs, "interval", args=(args.polldevs.name,), minutes=1, next_run_time=datetime.now()
    )

    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass

    return True


def parse_args():
    parser = argparse.ArgumentParser(description="Zino is not OpenView")
    parser.add_argument(
        "--polldevs", type=argparse.FileType("r"), metavar="PATH", default="polldevs.cf", help="Path to polldevs.cf"
    )

    args = parser.parse_args()
    if args.polldevs:
        args.polldevs.close()  # don't leave this temporary file descriptor open
    return args


if __name__ == "__main__":
    main()