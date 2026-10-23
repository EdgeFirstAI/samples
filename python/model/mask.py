# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

# NOTE: "model/mask" is disabled by default on EdgeFirst Perception 2.8+.
# Enable it by setting MASK_TOPIC=model/mask in /etc/default/model on the
# device, or use the "model/output" (Model) topic/sample instead.

import zenoh
from edgefirst.schemas.edgefirst_msgs import Mask
from argparse import ArgumentParser
import sys
import rerun as rr
import asyncio
import time
import threading
import numpy as np


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


def mask_worker(msg):
    try:
        mask = Mask.from_cdr(msg.payload.to_bytes())
    except Exception as e:
        print(f"Error processing Model Mask: {e}", file=sys.stderr)
        return

    np_arr = np.asarray(mask.mask, dtype=np.uint8)
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


async def main_async(args):
    # Setup rerun
    args.memory_limit = 10
    rr.script_setup(args, "model-mask")

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

    session.declare_subscriber(
        f"{topic_prefix(args.remote)}/model/mask", drain.callback
    )
    await asyncio.gather((mask_handler(drain)))

    while True:
        asyncio.sleep(0.001)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Mask")
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
