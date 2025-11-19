# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

import zenoh
from edgefirst.schemas.edgefirst_msgs import Mask
import rerun as rr
from argparse import ArgumentParser
import sys
import numpy as np
import asyncio
import time
import threading


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


def model_output_worker(msg):
    mask = Mask.deserialize(msg.payload.to_bytes())
    np_arr = np.asarray(mask.mask, dtype=np.uint8)
    np_arr = np.reshape(np_arr, [mask.height, mask.width, -1])
    np_arr = np.argmax(np_arr, axis=2)
    rr.log(
        "/",
        rr.AnnotationContext(
            [(0, "background", (0, 0, 0)), (1, "person", (255, 0, 0))]
        ),
    )
    rr.log("mask", rr.SegmentationImage(np_arr))


async def model_output_handler(drain):
    while True:
        msg = await drain.get_latest()
        thread = threading.Thread(target=model_output_worker, args=[msg])
        thread.start()

        while thread.is_alive():
            await asyncio.sleep(0.001)
        thread.join()


async def main_async(args):
    # Setup rerun
    args.memory_limit = 10
    rr.script_setup(args, "fusion/model_output")

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

    session.declare_subscriber("rt/fusion/model_output", drain.callback)
    await asyncio.gather((model_output_handler(drain)))

    while True:
        asyncio.sleep(0.001)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Fusion Model Output")
    parser.add_argument(
        "-r",
        "--remote",
        type=str,
        default=None,
        help="Connect to the remote endpoint instead of local.",
    )
    rr.script_add_args(parser)
    args = parser.parse_args()

    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
