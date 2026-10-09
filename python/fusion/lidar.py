# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

import zenoh
from edgefirst.schemas.sensor_msgs import PointCloud2
from argparse import ArgumentParser
import sys
import rerun as rr
import asyncio
import time
import threading
import struct
import colorsys


class Point:
    def __init__(self):
        self.x = 0
        self.y = 0
        self.z = 0
        self.fields = dict()


SIZE_OF_DATATYPE = [
    0,
    1,  # pub const INT8: u8= 1
    1,  # pub const UINT8: u8= 2
    2,  # pub const INT16: u8= 3
    2,  # pub const UINT16: u8= 4
    4,  # pub const INT32: u8= 5
    4,  # pub const UINT32: u8= 6
    4,  # pub const FLOAT32: u8= 7
    8,  # pub const FLOAT64: u8 = 8
]

STRUCT_LETTER_OF_DATATYPE = [
    "",
    "b",  # pub const INT8: u8= 1
    "B",  # pub const UINT8: u8= 2
    "h",  # pub const INT16: u8= 3
    "H",  # pub const UINT16: u8= 4
    "i",  # pub const INT32: u8= 5
    "I",  # pub const UINT32: u8= 6
    "f",  # pub const FLOAT32: u8= 7
    "d",  # pub const FLOAT64: u8 = 8
]


def decode_pcd(pcd: PointCloud2) -> list[Point]:
    points = []
    data = pcd.data.tobytes()
    endian_format = ">" if pcd.is_bigendian else "<"
    for i in range(pcd.height):
        for j in range(pcd.width):
            point = Point()
            point_start = (i * pcd.width + j) * pcd.point_step
            # Loop through the provided Fields for each Point (x, y, z, speed,
            # power, rcs)
            for f in pcd.fields:
                val = 0
                # Decode the data according to the datatype and endian format stated
                # in the message, location in the array block determined
                # through the offset
                arr = bytearray(
                    data[(point_start + f.offset):(point_start + f.offset + SIZE_OF_DATATYPE[f.datatype])])
                val = struct.unpack(
                    f'{endian_format}{STRUCT_LETTER_OF_DATATYPE[f.datatype]}', arr)[0]
                if f.name == "x":
                    point.x = val
                elif f.name == "y":
                    point.y = val
                elif f.name == "z":
                    point.z = val
                else:
                    point.fields[f.name] = val
            points.append(point)
    return points


def colormap(cmap, x):
    x = max(0.0, min(1.0, x))
    a = int(x * 255.0)
    b = min(255, a + 1)
    frac = x * 255.0 - a
    return [cmap[a][c] + frac * (cmap[b][c] - cmap[a][c]) for c in range(3)]


# Rainbow gradient used in place of the Turbo colormap previously bundled
# with edgefirst.schemas (removed upstream).
turbo_colormap = [colorsys.hsv_to_rgb(0.68 * (1.0 - i / 255.0), 1.0, 1.0) for i in range(256)]


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


def lidar_worker(msg):
    try:
        pcd = PointCloud2.from_cdr(msg.payload.to_bytes())
    except Exception as e:
        print(f"Error processing Fusion Lidar: {e}", file=sys.stderr)
        return

    points = decode_pcd(pcd)
    clusters = [p for p in points if p.cluster_id > 0]
    if not clusters:
        rr.log("fusion/lidar", rr.Points3D([], colors=[]))
        return
    max_id = max(p.cluster_id for p in clusters)
    pos = [[p.x, p.y, p.z] for p in clusters]
    colors = [colormap(turbo_colormap, p.cluster_id / max_id) for p in clusters]
    rr.log("fusion/lidar", rr.Points3D(pos, colors=colors))


async def lidar_handler(drain):
    while True:
        msg = await drain.get_latest()
        thread = threading.Thread(target=lidar_worker, args=[msg])
        thread.start()

        while thread.is_alive():
            await asyncio.sleep(0.001)
        thread.join()


async def main_async(args):
    # Setup rerun
    args.memory_limit = 10
    rr.script_setup(args, "fusion-lidar")

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

    session.declare_subscriber(f"{topic_prefix(args.remote)}/fusion/lidar", drain.callback)
    await asyncio.gather((lidar_handler(drain)))

    while True:
        asyncio.sleep(0.001)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Fusion - Lidar")
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
