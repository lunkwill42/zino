#!/usr/bin/env python3
import argparse
import asyncio
import logging
from datetime import datetime, timedelta

import tzlocal

from zino import state
from zino.api.legacy import ZinoTestProtocol
from zino.config.models import DEFAULT_INTERVAL_MINUTES
from zino.scheduler import get_scheduler, load_and_schedule_polldevs

STATE_DUMP_JOB_ID = "zino.dump_state"
# Never try to dump state more often than this:
MINIMUM_STATE_DUMP_INTERVAL = timedelta(seconds=10)
_log = logging.getLogger("zino")


def main():
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO if not args.debug else logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(name)s (%(threadName)s) - %(message)s",
    )
    state.state = state.ZinoState.load_state_from_file() or state.ZinoState()
    init_event_loop(args)


def init_event_loop(args: argparse.Namespace):
    scheduler = get_scheduler()
    scheduler.start()

    scheduler.add_job(
        func=load_and_schedule_polldevs,
        trigger="interval",
        args=(args.polldevs.name,),
        minutes=1,
        next_run_time=datetime.now(),
    )
    # Schedule state dumping every DEFAULT_INTERVAL_MINUTES and reschedule whenever events are committed
    scheduler.add_job(
        func=state.state.dump_state_to_file, trigger="interval", id=STATE_DUMP_JOB_ID, minutes=DEFAULT_INTERVAL_MINUTES
    )
    state.state.events.add_event_observer(reschedule_dump_state_on_commit)

    loop = asyncio.get_event_loop()
    server = loop.create_server(lambda: ZinoTestProtocol(state=state.state), "127.0.0.1", 8001)
    server_setup_result = loop.run_until_complete(server)
    _log.info("Serving on %r", server_setup_result.sockets[0].getsockname())

    if args.stop_in:
        _log.info("Instructed to stop in %s seconds", args.stop_in)
        scheduler.add_job(func=loop.stop, trigger="date", run_date=datetime.now() + timedelta(seconds=args.stop_in))

    try:
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass

    return True


def reschedule_dump_state_on_commit(event_id: int, max_wait: timedelta = MINIMUM_STATE_DUMP_INTERVAL):
    """Observer that reschedules the state dumper job whenever an event is committed and there's more than `max_wait`
    time until the next scheduled state dump.
    """
    scheduler = get_scheduler()
    job = scheduler.get_job(job_id=STATE_DUMP_JOB_ID)
    next_run = datetime.now(tz=tzlocal.get_localzone()) + max_wait
    if job.next_run_time > next_run:
        _log.debug("event %s committed, rescheduling state dump from %s to %s", event_id, job.next_run_time, next_run)
        job.modify(next_run_time=next_run)


def parse_args(arguments=None):
    parser = argparse.ArgumentParser(description="Zino is not OpenView")
    parser.add_argument(
        "--polldevs", type=argparse.FileType("r"), metavar="PATH", default="polldevs.cf", help="Path to polldevs.cf"
    )
    parser.add_argument(
        "--debug", action="store_true", default=False, help="Set global log level to DEBUG. Very chatty!"
    )
    parser.add_argument("--stop-in", type=int, default=None, help="Stop zino after N seconds.", metavar="N")
    args = parser.parse_args(args=arguments)
    if args.polldevs:
        args.polldevs.close()  # don't leave this temporary file descriptor open
    return args


if __name__ == "__main__":
    main()
