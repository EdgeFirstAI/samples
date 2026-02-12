# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

"""EdgeFirst Samples - Camera Info (Zenoh).

Subscribes to the Zenoh topic `rt/camera/info`, deserializes `CameraInfo` messages,
and logs basic camera properties (width/height) to a Rerun viewer.

Use `--remote <IP:PORT>` to connect to a remote Zenoh endpoint, otherwise local
discovery is used.
"""

import asyncio
from argparse import ArgumentParser
import sys
import threading

import rerun as rr
import zenoh

from edgefirst.schemas.sensor_msgs import CameraInfo


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
    info = CameraInfo.deserialize(msg.payload.to_bytes())
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


async def main_async(session):
    # Create drains
    loop = asyncio.get_running_loop()
    drain = MessageDrain(loop)

    session.declare_subscriber("rt/camera/info", drain.callback)
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
        help="Connect to the remote endpoint instead of local.",
    )
    rr.script_add_args(parser)
    args = parser.parse_args()

    # Setup rerun
    args.memory_limit = 10
    rr.script_setup(args, sys.argv[0])

    # Zenoh config
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    if args.remote:
        # Ensure remote endpoint has tcp/ prefix
        remote = args.remote if args.remote.startswith("tcp/") else f"tcp/{args.remote}"
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", f'{{"endpoints": ["{remote}"]}}')
    session = zenoh.open(config)

    try:
        asyncio.run(main_async(session))
    except KeyboardInterrupt:
        session.close()
        sys.exit(0)
    session.close()


if __name__ == "__main__":
    main()
