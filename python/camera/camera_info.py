# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

import zenoh
from edgefirst.schemas.sensor_msgs import CameraInfo
import rerun as rr
from argparse import ArgumentParser
import sys
import asyncio
import time
import threading


def topic_prefix(remote):
    # Topics are published under "<hostname>/..."; use "*" to match any host locally.
    if not remote:
        return "*"
    return remote.split("/")[-1].split(":")[0]


class MessageDrain:
    def __init__(self, loop):
        self._queue = asyncio.Queue(maxsize=100)
        self._loop = loop

    def callback(self, msg):
        if not self._loop.is_closed():
            if self._queue.full():
                self._queue.get_nowait()
            self._loop.call_soon_threadsafe(self._queue.put_nowait, msg)

    async def read(self):
        return await self._queue.get()

    async def get_latest(self):
        latest = await self._queue.get()
        while not self._queue.empty():
            latest = self._queue.get_nowait()
        return latest


def info_worker(msg):
    try:
        info = CameraInfo.from_cdr(msg.payload.to_bytes())
    except Exception as e:
        print(f"Error processing Camera Info: {e}", file=sys.stderr)
        return

    width = info.width
    height = info.height
    rr.log(
        "CameraInfo", rr.TextLog("Camera Width: %d Camera Height: %d" % (width, height))
    )


async def info_handler(drain):
    while True:
        msg = await drain.get_latest()
        thread = threading.Thread(target=info_worker, args=[msg])
        thread.start()

        while thread.is_alive():
            await asyncio.sleep(0.001)
        thread.join()


async def main_async(args):
    # Setup rerun
    args.memory_limit = 10
    rr.script_setup(args, "camera-info")

    # Zenoh config
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    if args.remote:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", f'{{"endpoints": ["{args.remote}"]}}')
    session = zenoh.open(config)

    # Create drains
    loop = asyncio.get_running_loop()
    drain = MessageDrain(loop)

    session.declare_subscriber(f"{topic_prefix(args.remote)}/camera/info", drain.callback)
    await asyncio.gather((info_handler(drain)))

    while True:
        asyncio.sleep(0.001)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Camera Info")
    parser.add_argument(
        "-r",
        "--remote",
        type=str,
        default=None,
        help=(
            "Connect to the remote endpoint using its hostname, not its IP "
            "address (e.g. maivin-1234:7447), since topics are published "
            'under "<hostname>/<topic>" and the hostname is needed to find '
            "them."
        ),
    )
    rr.script_add_args(parser)
    args = parser.parse_args()

    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
