# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

# "model/output" (edgefirst_msgs/Model) is the default model topic on
# EdgeFirst Perception 2.8+, combining detection boxes and segmentation
# masks in one message. The legacy "model/boxes2d", "model/mask" and
# "model/mask_compressed" topics are disabled by default; see boxes2d.py,
# boxes2d_tracked.py, mask.py and compressed_mask.py for the opt-in steps.

import zenoh
from edgefirst.schemas.edgefirst_msgs import Model
from argparse import ArgumentParser
import sys
import rerun as rr
import asyncio
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


def output_worker(msg):
    try:
        model = Model.from_cdr(msg.payload.to_bytes())
    except Exception as e:
        print(f"Error processing Model Output: {e}", file=sys.stderr)
        return

    centers = []
    sizes = []
    labels = []
    for box in model.boxes:
        centers.append((box.center_x, box.center_y))
        sizes.append((box.width, box.height))
        labels.append(box.label)
    rr.log("boxes", rr.Boxes2D(centers=centers, sizes=sizes, labels=labels))

    for mask in model.masks:
        np_arr = np.frombuffer(mask.mask, dtype=np.uint8)
        np_arr = np.reshape(np_arr, [mask.height, mask.width, -1])
        np_arr = np.argmax(np_arr, axis=2)
        rr.log("mask", rr.SegmentationImage(np_arr))


async def output_handler(drain):
    rr.log(
        "/",
        rr.AnnotationContext(
            [(0, "background", (0, 0, 0)), (1, "person", (0, 255, 0))]
        ),
    )
    while True:
        msg = await drain.get_latest()
        thread = threading.Thread(target=output_worker, args=[msg])
        thread.start()

        while thread.is_alive():
            await asyncio.sleep(0.001)
        thread.join()


async def main_async(args):
    # Setup rerun
    args.memory_limit = 10
    rr.script_setup(args, "model-output")

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
        f"{topic_prefix(args.remote)}/model/output", drain.callback
    )
    await asyncio.gather((output_handler(drain)))

    while True:
        asyncio.sleep(0.001)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Model Output")
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
