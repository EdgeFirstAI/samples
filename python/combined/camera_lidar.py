# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

from argparse import ArgumentParser
import asyncio
import io
import sys
import av
import zenoh
import threading
import time
from collections import deque
import numpy as np
import rerun as rr
import rerun.blueprint as rrb
from edgefirst.schemas.edgefirst_msgs import Detect
from edgefirst.schemas.sensor_msgs import PointCloud2
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


class FrameSize:
    def __init__(self):
        self._size = []
        self._event = asyncio.Event()

    def set(self, width, height):
        self._size = [width, height]
        if not self._event.is_set():
            self._event.set()

    async def get(self):
        await self._event.wait()
        return self._size


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


def h264_worker(msg, frame_storage, raw_data, container):
    raw_data.write(msg.payload.to_bytes())
    raw_data.seek(0)
    for packet in container.demux():
        try:
            if packet.size == 0:
                continue
            raw_data.seek(0)
            raw_data.truncate(0)
            for frame in packet.decode():
                frame_array = frame.to_ndarray(format="rgb24")
                frame_storage.set(frame_array.shape[1], frame_array.shape[0])
                rr.log("/camera", rr.Image(frame_array))
        except Exception:
            continue


async def h264_handler(drain, frame_storage):
    raw_data = io.BytesIO()
    container = av.open(raw_data, format="h264", mode="r")

    while True:
        msg = await drain.get_latest()
        thread = threading.Thread(
            target=h264_worker, args=[msg, frame_storage, raw_data, container]
        )
        thread.start()

        while thread.is_alive():
            await asyncio.sleep(0.001)
        thread.join()


def boxes2d_worker(msg, boxes_tracked, frame_size):
    try:
        detection = Detect.from_cdr(msg.payload.to_bytes())
    except Exception as e:
        print(f"Error processing Detection: {e}", file=sys.stderr)
        return

    centers, sizes, labels, colors = [], [], [], []
    for box in detection.boxes:
        if box.track_id and box.track_id not in boxes_tracked:
            boxes_tracked[box.track_id] = [
                box.label + ": " + box.track_id[:6],
                list(np.random.choice(range(256), size=3)),
            ]
        if box.track_id:
            colors.append(boxes_tracked[box.track_id][1])
            labels.append(boxes_tracked[box.track_id][0])
        else:
            colors.append([0, 255, 0])
            labels.append(box.label)
        centers.append(
            (int(box.center_x * frame_size[0]), int(box.center_y * frame_size[1]))
        )
        sizes.append((int(box.width * frame_size[0]), int(box.height * frame_size[1])))
    rr.log(
        "/camera/boxes",
        rr.Boxes2D(centers=centers, sizes=sizes, labels=labels, colors=colors),
    )


async def boxes2d_handler(drain, frame_storage):
    boxes_tracked = {}
    _ = await frame_storage.get()
    while True:
        msg = await drain.get_latest()
        frame_size = await frame_storage.get()
        thread = threading.Thread(
            target=boxes2d_worker, args=[msg, boxes_tracked, frame_size]
        )
        thread.start()

        while thread.is_alive():
            await asyncio.sleep(0.001)
        thread.join()


def clusters_worker(msg):
    try:
        pcd = PointCloud2.from_cdr(msg.payload.to_bytes())
    except Exception as e:
        print(f"Error processing Lidar Clusters: {e}", file=sys.stderr)
        return

    points = decode_pcd(pcd)
    clusters = [p for p in points if p.cluster_id > 0]
    if not clusters:
        rr.log("/pointcloud/clusters", rr.Points3D([], colors=[]))
        return
    max_id = max(p.cluster_id for p in clusters)
    pos = [[p.x, p.y, p.z] for p in clusters]
    colors = [colormap(turbo_colormap, p.cluster_id / max_id) for p in clusters]
    rr.log("/pointcloud/clusters", rr.Points3D(pos, colors=colors))


async def clusters_handler(drain):
    while True:
        msg = await drain.get_latest()
        thread = threading.Thread(target=clusters_worker, args=[msg])
        thread.start()

        while thread.is_alive():
            await asyncio.sleep(0.001)
        thread.join()


async def main_async(args):
    # Setup rerun
    # args.memory_limit = 10
    rr.script_setup(args, "camera-lidar")

    blueprint = rrb.Blueprint(
        rrb.Grid(
            contents=[
                rrb.Spatial2DView(origin="/camera", name="Camera Feed"),
                rrb.Spatial3DView(origin="/pointcloud", name="Pointcloud Clusters"),
            ]
        )
    )
    rr.send_blueprint(blueprint)

    # Zenoh config
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    if args.remote:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", f'{{"endpoints": ["{args.remote}"]}}')
    session = zenoh.open(config)

    # Create drains
    loop = asyncio.get_running_loop()
    h264_drain = MessageDrain(loop)
    boxes2d_drain = MessageDrain(loop)
    lidar_drain = MessageDrain(loop)
    frame_size_storage = FrameSize()

    # Declare subscribers
    host = topic_prefix(args.remote)
    session.declare_subscriber(f"{host}/camera/h264", h264_drain.callback)
    # NOTE: "model/boxes2d" is disabled by default on EdgeFirst Perception
    # 2.8+. Enable it with DETECT_TOPIC=model/boxes2d in /etc/default/model
    # on the device, or use the "model/output" (Model) topic/sample instead.
    session.declare_subscriber(f"{host}/model/boxes2d", boxes2d_drain.callback)
    session.declare_subscriber(f"{host}/lidar/clusters", lidar_drain.callback)

    # Launch concurrent processing tasks
    await asyncio.gather(
        h264_handler(h264_drain, frame_size_storage),
        boxes2d_handler(boxes2d_drain, frame_size_storage),
        clusters_handler(lidar_drain),
    )

    while True:
        asyncio.sleep(0.001)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Camera-Lidar")
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
