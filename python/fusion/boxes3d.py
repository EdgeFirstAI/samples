# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

import zenoh
from edgefirst.schemas.edgefirst_msgs import Detect
from argparse import ArgumentParser
import sys
import rerun as rr
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
            self._loop.call_soon_threadsafe(self._queue.put_nowait, msg)

    async def read(self):
        return await self._queue.get()

    async def get_latest(self):
        latest = await self._queue.get()
        while not self._queue.empty():
            latest = self._queue.get_nowait()
        return latest


def boxes3d_worker(msg):
    try:
        detection = Detect.from_cdr(msg.payload.to_bytes())
    except Exception as e:
        print(f"Error processing Fusion Boxes3D: {e}", file=sys.stderr)
        return

    # The 3D boxes are in an _optical frame of reference, where x is right, y is down, and z (distance) is forward
    # We will convert them to a normal frame of reference, where x is forward, y is left, and z is up
    centers = [(x.distance, -x.center_x, -x.center_y) for x in detection.boxes]
    sizes = [(x.width, x.width, x.height) for x in detection.boxes]

    rr.log("/pointcloud/fusion/boxes", rr.Boxes3D(centers=centers, sizes=sizes))


async def boxes3d_handler(drain):
    while True:
        msg = await drain.get_latest()
        thread = threading.Thread(target=boxes3d_worker, args=[msg])
        thread.start()

        while thread.is_alive():
            await asyncio.sleep(0.001)
        thread.join()


async def main_async(args):
    # Setup rerun
    args.memory_limit = 10
    rr.script_setup(args, "fusion-boxes3d")

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

    session.declare_subscriber(f"{topic_prefix(args.remote)}/fusion/boxes3d", drain.callback)
    await asyncio.gather((boxes3d_handler(drain)))

    while True:
        asyncio.sleep(0.001)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Boxes3D")
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
