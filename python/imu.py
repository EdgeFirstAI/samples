# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

import rerun as rr
import zenoh
import sys
import asyncio
import time
from argparse import ArgumentParser
from edgefirst.schemas.sensor_msgs import Imu
from rerun.datatypes import Quaternion
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


def imu_worker(msg):
    imu = Imu.deserialize(msg.payload.to_bytes())
    x = imu.orientation.x
    y = imu.orientation.y
    z = imu.orientation.z
    w = imu.orientation.w
    rr.log(
        "/imu", rr.Transform3D(quaternion=Quaternion(xyzw=[x, y, z, w]))
    )


async def imu_handler(drain):
    while True:
        msg = await drain.get_latest()
        thread = threading.Thread(target=imu_worker, args=[msg])
        thread.start()

        while thread.is_alive():
            await asyncio.sleep(0.001)
        thread.join()


async def main_async(args):
    # Setup rerun
    args.memory_limit = 10
    rr.script_setup(args, "imu")

    # Zenoh config
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    if args.remote:
        # Ensure remote endpoint has tcp/ prefix
        remote = args.remote if args.remote.startswith("tcp/") else f"tcp/{args.remote}"
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", f'{{"endpoints": ["{remote}"]}}')
    session = zenoh.open(config)

    # Create drains
    loop = asyncio.get_running_loop()
    drain = MessageDrain(loop)

    rr.log("/imu", rr.Boxes3D(half_sizes=[[0.5, 0.5, 0.5]], fill_mode="solid"))
    rr.log("/imu", rr.TransformAxes3D(axis_length=2))

    session.declare_subscriber("rt/imu", drain.callback)
    await asyncio.gather((imu_handler(drain)))

    while True:
        asyncio.sleep(0.001)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - IMU")
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
        rr.rerun_shutdown()
        sys.exit(0)


if __name__ == "__main__":
    main()
