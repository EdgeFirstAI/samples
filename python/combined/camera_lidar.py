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
from edgefirst.schemas import decode_pcd, colormap, turbo_colormap
import threading

def format_remote_endpoint(remote):
    if not remote:
        return None
    
    # Already in full format (tcp/IP:PORT)
    if remote.startswith("tcp/") and ":" in remote.split("/", 1)[1]:
        return remote
    
    # Just IP address (e.g., "10.10.41.100")
    if "/" not in remote and ":" not in remote:
        return f"tcp/{remote}:7447"
    
    # IP:PORT format (e.g., "10.10.41.100:7447")
    if ":" in remote and not remote.startswith("tcp/"):
        return f"tcp/{remote}"
    
    # tcp/IP format (e.g., "tcp/10.10.41.100")
    if remote.startswith("tcp/") and ":" not in remote.split("/", 1)[1]:
        return f"{remote}:7447"
    
    # Fallback: return as-is
    return remote

# Global variables for message storage
h264_msg = None
boxes2d_msg = None
lidar_msg = None

# Global for frame size tracking
frame_size = FrameSize()


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


def h264_handler(msg):
    """Simple sync handler that stores message in global."""
    global h264_msg
    h264_msg = msg


def boxes2d_handler(msg):
    """Simple sync handler that stores message in global."""
    global boxes2d_msg
    boxes2d_msg = msg


def clusters_handler(msg):
    """Simple sync handler that stores message in global."""
    global lidar_msg
    lidar_msg = msg


async def h264_worker():
    """Async worker that processes H.264 messages from global."""
    global h264_msg, frame_size
    raw_data = io.BytesIO()
    container = av.open(raw_data, format="h264", mode="r")
    
    while True:
        if h264_msg is not None:
            try:
                msg = h264_msg
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
                            frame_size.set(frame_array.shape[1], frame_array.shape[0])
                            rr.log("/camera", rr.Image(frame_array))
                    except Exception:
                        continue
            except Exception as e:
                print(f"Error processing H.264 message: {e}", file=sys.stderr)
        await asyncio.sleep(0.01)


async def boxes2d_worker():
    """Async worker that processes boxes2d messages from global."""
    global boxes2d_msg, frame_size
    boxes_tracked = {}
    _ = await frame_size.get()
    
    while True:
        if boxes2d_msg is not None:
            try:
                msg = boxes2d_msg
                detection = Detect.from_cdr(msg.payload.to_bytes())
                current_frame_size = await frame_size.get()
                centers, sizes, labels, colors = [], [], [], []
                for box in detection.boxes:
                    if box.track.id and box.track.id not in boxes_tracked:
                        boxes_tracked[box.track.id] = [
                            box.label + ": " + box.track.id[:6],
                            list(np.random.choice(range(256), size=3)),
                        ]
                    if box.track.id:
                        colors.append(boxes_tracked[box.track.id][1])
                        labels.append(boxes_tracked[box.track.id][0])
                    else:
                        colors.append([0, 255, 0])
                        labels.append(box.label)
                    centers.append(
                        (int(box.center_x * current_frame_size[0]), int(box.center_y * current_frame_size[1]))
                    )
                    sizes.append((int(box.width * current_frame_size[0]), int(box.height * current_frame_size[1])))
                rr.log(
                    "/camera/boxes",
                    rr.Boxes2D(centers=centers, sizes=sizes, labels=labels, colors=colors),
                )
            except Exception as e:
                print(f"Error processing boxes2d message: {e}", file=sys.stderr)
        await asyncio.sleep(0.01)


async def lidar_worker():
    """Async worker that processes LiDAR cluster messages from global."""
    global lidar_msg
    
    while True:
        if lidar_msg is not None:
            try:
                msg = lidar_msg
                pcd = PointCloud2.from_cdr(msg.payload.to_bytes())
                points = decode_pcd(pcd)
                clusters = [p for p in points if p.cluster_id > 0]
                if not clusters:
                    rr.log("/pointcloud/clusters", rr.Points3D([], colors=[]))
                else:
                    max_id = max(p.cluster_id for p in clusters)
                    pos = [[p.x, p.y, p.z] for p in clusters]
                    colors = [colormap(turbo_colormap, p.cluster_id / max_id) for p in clusters]
                    rr.log("/pointcloud/clusters", rr.Points3D(pos, colors=colors))
            except Exception as e:
                print(f"Error processing LiDAR cluster message: {e}", file=sys.stderr)
        await asyncio.sleep(0.01)


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
    remote = format_remote_endpoint(args.remote)
    if remote:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", f'{{"endpoints": ["{remote}"]}}')
    session = zenoh.open(config)

    # Declare subscribers with simple handlers
    session.declare_subscriber("rt/camera/h264", h264_handler)
    session.declare_subscriber("rt/model/boxes2d", boxes2d_handler)
    session.declare_subscriber("rt/lidar/clusters", clusters_handler)

    # Launch concurrent processing tasks
    try:
        await asyncio.gather(
            h264_worker(),
            boxes2d_worker(),
            lidar_worker(),
        )
    except KeyboardInterrupt:
        pass


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Camera-Lidar")
    parser.add_argument(
        "-r",
        "--remote",
        type=str,
        default=None,
        help="Remote endpoint (IP:PORT or just IP, defaults to port 7447)",
    )
    rr.script_add_args(parser)
    args = parser.parse_args()

    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
