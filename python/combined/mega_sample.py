# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

from argparse import ArgumentParser
import time
import rerun as rr
import rerun.blueprint as rrb
import zenoh
import ctypes
import os
import asyncio
import sys
import threading
import io
import av
import numpy as np
from edgefirst.schemas.sensor_msgs import PointCloud2
from edgefirst.schemas import decode_pcd, colormap, turbo_colormap

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

# Constants for syscall
SYS_pidfd_open = 434  # From syscall.h
SYS_pidfd_getfd = 438  # From syscall.h
GETFD_FLAGS = 0

# C bindings to syscall (Linux only)
if sys.platform.startswith("linux"):
    libc = ctypes.CDLL("libc.so.6", use_errno=True)


def pidfd_open(pid: int, flags: int = 0) -> int:
    return libc.syscall(SYS_pidfd_open, pid, flags)


def pidfd_getfd(pidfd: int, target_fd: int, flags: int = GETFD_FLAGS) -> int:
    return libc.syscall(SYS_pidfd_getfd, pidfd, target_fd, flags)


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


# Global variables for message storage
h264_msg = None
dma_msg = None
jpeg_msg = None
boxes2d_msg = None
mask_msg = None
gps_msg = None
boxes3d_msg = None
radar_msg = None
lidar_msg = None

# Global for frame size tracking
frame_size = FrameSize()


def h264_handler(msg):
    """Simple sync handler that stores message in global."""
    global h264_msg
    h264_msg = msg


def dma_handler(msg):
    """Simple sync handler that stores message in global."""
    global dma_msg
    dma_msg = msg


def jpeg_handler(msg):
    """Simple sync handler that stores message in global."""
    global jpeg_msg
    jpeg_msg = msg


def boxes2d_handler(msg):
    """Simple sync handler that stores message in global."""
    global boxes2d_msg
    boxes2d_msg = msg


def mask_handler(msg):
    """Simple sync handler that stores message in global."""
    global mask_msg
    mask_msg = msg


def gps_handler(msg):
    """Simple sync handler that stores message in global."""
    global gps_msg
    gps_msg = msg


def boxes3d_handler(msg):
    """Simple sync handler that stores message in global."""
    global boxes3d_msg
    boxes3d_msg = msg


def radar_handler(msg):
    """Simple sync handler that stores message in global."""
    global radar_msg
    radar_msg = msg


def lidar_handler(msg):
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


async def dma_worker():
    """Async worker that processes DMA messages from global."""
    global dma_msg, frame_size
    from edgefirst.schemas.edgefirst_msgs import DmaBuffer
    import mmap

    while True:
        if dma_msg is not None:
            try:
                msg = dma_msg
                dma_buf = DmaBuffer.from_cdr(msg.payload.to_bytes())
                pidfd = pidfd_open(dma_buf.pid)
                if pidfd < 0:
                    await asyncio.sleep(0.01)
                    continue

                fd = pidfd_getfd(pidfd, dma_buf.fd, GETFD_FLAGS)
                if fd < 0:
                    await asyncio.sleep(0.01)
                    continue

                frame_size.set(dma_buf.width, dma_buf.height)
                # Now fd can be used as a file descriptor
                mm = mmap.mmap(fd, dma_buf.length)
                rr.log(
                    "/camera",
                    rr.Image(
                        bytes=mm[:],
                        width=dma_buf.width,
                        height=dma_buf.height,
                        pixel_format=rr.PixelFormat.YUY2,
                    ),
                )
                mm.close()
                os.close(fd)
                os.close(pidfd)
            except Exception as e:
                print(f"Error processing DMA message: {e}", file=sys.stderr)
        await asyncio.sleep(0.01)


async def jpeg_worker():
    """Async worker that processes JPEG messages from global."""
    global jpeg_msg, frame_size
    import numpy as np
    import cv2
    from edgefirst.schemas.sensor_msgs import CompressedImage

    while True:
        if jpeg_msg is not None:
            try:
                msg = jpeg_msg
                image = CompressedImage.from_cdr(msg.payload.to_bytes())
                np_arr = np.frombuffer(bytearray(image.data), np.uint8)
                im = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                im = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
                frame_size.set(im.shape[0], im.shape[1])
                rr.log("/camera", rr.Image(im))
            except Exception as e:
                print(f"Error processing JPEG message: {e}", file=sys.stderr)
        await asyncio.sleep(0.01)


async def boxes2d_worker():
    """Async worker that processes boxes2d messages from global."""
    global boxes2d_msg, frame_size
    from edgefirst.schemas.edgefirst_msgs import Detect
    
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
                rr.log("/camera/boxes", rr.Boxes2D(centers=centers, sizes=sizes, labels=labels))
                rr.log(
                    "/metrics/detection_inference",
                    rr.Scalars(
                        float(detection.model_time.sec) + float(detection.model_time.nanosec / 1e9)
                    ),
                )
            except Exception as e:
                print(f"Error processing boxes2d message: {e}", file=sys.stderr)
        await asyncio.sleep(0.01)


async def mask_worker(remote):
    """Async worker that processes mask messages from global."""
    global mask_msg, frame_size
    from edgefirst.schemas.edgefirst_msgs import Mask
    import zstd
    import numpy as np
    import cv2

    _ = await frame_size.get()
    rr.log(
        "/",
        rr.AnnotationContext(
            [(0, "background", (0, 0, 0)), (1, "person", (0, 255, 0))]
        ),
    )
    
    while True:
        if mask_msg is not None:
            try:
                msg = mask_msg
                mask = Mask.from_cdr(msg.payload.to_bytes())
                current_frame_size = await frame_size.get()
                if remote:
                    decoded_array = zstd.decompress(bytes(mask.mask))
                    np_arr = np.frombuffer(decoded_array, np.uint8).reshape(
                        mask.height, mask.width, -1
                    )
                else:
                    np_arr = np.asarray(mask.mask, dtype=np.uint8)
                    np_arr = np.reshape(np_arr, [mask.height, mask.width, -1])
                np_arr = cv2.resize(np_arr, current_frame_size)
                np_arr = np.argmax(np_arr, axis=2)
                rr.log("/camera/mask", rr.SegmentationImage(np_arr))
            except Exception as e:
                print(f"Error processing mask message: {e}", file=sys.stderr)
        await asyncio.sleep(0.01)


async def gps_worker():
    """Async worker that processes GPS messages from global."""
    global gps_msg
    from edgefirst.schemas.sensor_msgs import NavSatFix

    while True:
        if gps_msg is not None:
            try:
                msg = gps_msg
                gps = NavSatFix.from_cdr(msg.payload.to_bytes())
                rr.log("/gps", rr.GeoPoints(lat_lon=[gps.latitude, gps.longitude]))
            except Exception as e:
                print(f"Error processing GPS message: {e}", file=sys.stderr)
        await asyncio.sleep(0.01)


async def boxes3d_worker():
    """Async worker that processes 3D boxes messages from global."""
    global boxes3d_msg
    from edgefirst.schemas.edgefirst_msgs import Detect

    while True:
        if boxes3d_msg is not None:
            try:
                msg = boxes3d_msg
                detection = Detect.from_cdr(msg.payload.to_bytes())
                # The 3D boxes are in an _optical frame of reference, where x is right, y is down, and z (distance) is forward
                # We will convert them to a normal frame of reference, where x is forward, y is left, and z is up
                centers = [(x.distance, -x.center_x, -x.center_y) for x in detection.boxes]
                sizes = [(x.width, x.width, x.height) for x in detection.boxes]
                rr.log("/pointcloud/fusion/boxes", rr.Boxes3D(centers=centers, sizes=sizes))
            except Exception as e:
                print(f"Error processing 3D boxes message: {e}", file=sys.stderr)
        await asyncio.sleep(0.01)


async def radar_worker():
    """Async worker that processes radar cluster messages from global."""
    global radar_msg
    
    while True:
        if radar_msg is not None:
            try:
                msg = radar_msg
                pcd = PointCloud2.from_cdr(msg.payload.to_bytes())
                points = decode_pcd(pcd)
                clusters = [p for p in points if p.cluster_id > 0]
                if not clusters:
                    rr.log("/pointcloud/radar/clusters", rr.Points3D([], colors=[]))
                else:
                    max_id = max(p.cluster_id for p in clusters)
                    pos = [[p.x, p.y, p.z] for p in clusters]
                    colors = [colormap(turbo_colormap, p.cluster_id / max_id) for p in clusters]
                    rr.log("/pointcloud/radar/clusters", rr.Points3D(pos, colors=colors))
            except Exception as e:
                print(f"Error processing radar cluster message: {e}", file=sys.stderr)
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
                    rr.log("/pointcloud/lidar/clusters", rr.Points3D([], colors=[]))
                else:
                    max_id = max(p.cluster_id for p in clusters)
                    pos = [[p.x, p.y, p.z] for p in clusters]
                    colors = [colormap(turbo_colormap, p.cluster_id / max_id) for p in clusters]
                    rr.log("/pointcloud/lidar/clusters", rr.Points3D(pos, colors=colors))
            except Exception as e:
                print(f"Error processing LiDAR cluster message: {e}", file=sys.stderr)
        await asyncio.sleep(0.01)


async def main_async(args):
    # Setup rerun
    args.memory_limit = 10
    # Create the default Zenoh configuration and if the remote argument is
    # provided set the mode to client and add the target to the endpoints.
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    remote = format_remote_endpoint(args.remote)
    if remote is not None:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", '{"endpoints": ["%s"]}' % remote)
    session = zenoh.open(config)

    # Create a subscriber for all topics matching the pattern "rt/**"
    subscriber = session.declare_subscriber("rt/**")

    # Keep a list of discovered topics to avoid noise from duplicates
    camera_topics = set()
    model_topics = set()
    radar_topics = set()
    fusion_topics = set()
    lidar_topics = set()
    misc_topics = set()
    start = time.time()

    print("Gathering available topics")
    while True:
        if time.time() - start >= 5:
            break
        msg = subscriber.recv()

        # Ignore message if the topic is known otherwise save the topic
        topic = str(msg.key_expr)
        if "rt/camera" in topic:
            if topic not in camera_topics:
                camera_topics.add(topic)
        elif "rt/model" in topic:
            if topic not in model_topics:
                model_topics.add(topic)
        elif "rt/radar" in topic:
            if topic not in radar_topics:
                radar_topics.add(topic)
        elif "rt/fusion" in topic:
            if topic not in fusion_topics:
                fusion_topics.add(topic)
        elif "rt/lidar" in topic:
            if topic not in lidar_topics:
                lidar_topics.add(topic)
        else:
            if topic not in misc_topics:
                misc_topics.add(topic)

    subscriber.undeclare()
    del subscriber

    args.memory_limit = 10
    rr.script_setup(args, "mega_sample")
    blueprint = rrb.Blueprint(
        rrb.Grid(
            contents=[
                rrb.MapView(origin="/gps", name="GPS"),
                rrb.Spatial2DView(origin="/camera", name="Camera Feed"),
                rrb.Spatial3DView(origin="/pointcloud", name="Pointcloud Clusters"),
                rrb.TimeSeriesView(origin="/metrics", name="Model Information"),
            ]
        )
    )
    rr.send_blueprint(blueprint)

    async_funcs = []

    cam_topic = None
    if remote is None and "rt/camera/dma" in camera_topics:
        cam_topic = "rt/camera/dma"
        session.declare_subscriber(cam_topic, dma_handler)
        async_funcs.append(dma_worker())
    elif "rt/camera/h264" in camera_topics:
        cam_topic = "rt/camera/h264"
        session.declare_subscriber(cam_topic, h264_handler)
        async_funcs.append(h264_worker())
    elif "rt/camera/jpeg" in camera_topics:
        cam_topic = "rt/camera/jpeg"
        session.declare_subscriber(cam_topic, jpeg_handler)
        async_funcs.append(jpeg_worker())
    else:
        print("No camera topic available")

    if "rt/model/boxes2d" in model_topics:
        session.declare_subscriber("rt/model/boxes2d", boxes2d_handler)
        async_funcs.append(boxes2d_worker())

    if remote is None and "rt/model/mask" in model_topics:
        session.declare_subscriber("rt/model/mask", mask_handler)
    elif remote is not None and "rt/model/mask_compressed" in model_topics:
        session.declare_subscriber("rt/model/mask_compressed", mask_handler)
    elif "rt/model/mask" in model_topics:
        session.declare_subscriber("rt/model/mask", mask_handler)
    elif "rt/model/mask_compressed" in model_topics:
        session.declare_subscriber("rt/model/mask_compressed", mask_handler)

    if "rt/model/mask" in model_topics or "rt/model/mask_compressed" in model_topics:
        async_funcs.append(mask_worker(remote))

    if "rt/gps" in misc_topics:
        session.declare_subscriber("rt/gps", gps_handler)
        async_funcs.append(gps_worker())

    if "rt/fusion/boxes3d" in fusion_topics:
        session.declare_subscriber("rt/fusion/boxes3d", boxes3d_handler)
        async_funcs.append(boxes3d_worker())

    if "rt/radar/clusters" in radar_topics:
        session.declare_subscriber("rt/radar/clusters", radar_handler)
        async_funcs.append(radar_worker())

    if "rt/lidar/clusters" in lidar_topics:
        session.declare_subscriber("rt/lidar/clusters", lidar_handler)
        async_funcs.append(lidar_worker())

    # Launch concurrent processing tasks
    try:
        await asyncio.gather(*async_funcs)
    except KeyboardInterrupt:
        pass


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Mega Sample")
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
