# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

"""
Subscribes to Zenoh topics to fetch and visualize LiDAR reflectivity images.

- Receives Image messages from EdgeFirst schemas
- Processes mono8-encoded reflectivity images for visualization in Rerun
- Supports both remote and local Zenoh endpoints
"""

import sys
import threading
import asyncio
from argparse import ArgumentParser

import numpy as np
import zenoh
import rerun as rr
from edgefirst.schemas.sensor_msgs import Image


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


def reflect_worker(msg):
    reflect = Image.deserialize(msg.payload.to_bytes())

    # Process reflect image
    if reflect.encoding != "mono8":
        print("Reflect encoding is not mono8")
        return

    data = (
        np.array(
            reflect.data).reshape(
            (reflect.height,
             reflect.width)).astype(
            np.uint8)
    )
    rr.log("lidar/depth", rr.Image(data))


async def reflect_handler(drain):
    while True:
        msg = await drain.get_latest()
        thread = threading.Thread(target=reflect_worker, args=[msg])
        thread.start()

        while thread.is_alive():
            await asyncio.sleep(0.001)
        thread.join()


async def main_async(session):
    # Create drains
    loop = asyncio.get_running_loop()
    drain = MessageDrain(loop)

    session.declare_subscriber("rt/lidar/reflect", drain.callback)
    await asyncio.gather((reflect_handler(drain)))

    while True:
        asyncio.sleep(0.001)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Lidar Reflect")
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
        remote = args.remote if args.remote.startswith(
            "tcp/") else f"tcp/{args.remote}"
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
