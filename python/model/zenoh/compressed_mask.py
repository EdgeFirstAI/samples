# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

"""
Subscribes to a Zenoh topic to fetch and visualize compressed output masks.

- Receives serialized Mask messages from EdgeFirst schemas
- Decompresses mask data using zstd
- Uses Rerun for visualization
- Supports both remote and local Zenoh endpoints
"""

import sys
import threading
import asyncio
from argparse import ArgumentParser

import zstd
import numpy as np
import zenoh
import rerun as rr
from edgefirst.schemas.edgefirst_msgs import Mask


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


def mask_worker(msg):
    mask = Mask.deserialize(msg.payload.to_bytes())
    decoded_array = zstd.decompress(bytes(mask.mask))
    np_arr = np.frombuffer(decoded_array, np.uint8)
    np_arr = np.reshape(np_arr, [mask.height, mask.width, -1])
    np_arr = np.argmax(np_arr, axis=2)

    rr.log("mask", rr.SegmentationImage(np_arr))


async def mask_handler(drain):
    rr.log(
        "/",
        rr.AnnotationContext(
            [(0, "background", (0, 0, 0)), (1, "person", (0, 255, 0))]
        ),
    )
    while True:
        msg = await drain.get_latest()
        thread = threading.Thread(target=mask_worker, args=[msg])
        thread.start()

        while thread.is_alive():
            await asyncio.sleep(0.001)
        thread.join()


async def main_async(session):
    # Create drains
    loop = asyncio.get_running_loop()
    drain = MessageDrain(loop)

    session.declare_subscriber("rt/model/mask_compressed", drain.callback)
    await asyncio.gather((mask_handler(drain)))

    while True:
        asyncio.sleep(0.001)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Mask Compressed")
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
