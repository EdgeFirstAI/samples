from argparse import ArgumentParser
import time
import rerun as rr
import rerun.blueprint as rrb
import zenoh
import ctypes
import os
import asyncio
import sys

# Constants for syscall
SYS_pidfd_open = 434  # From syscall.h
SYS_pidfd_getfd = 438 # From syscall.h
GETFD_FLAGS = 0

# C bindings to syscall (Linux only)
if sys.platform.startswith('linux'):
    libc = ctypes.CDLL("libc.so.6", use_errno=True)

def pidfd_open(pid: int, flags: int = 0) -> int:
    return libc.syscall(SYS_pidfd_open, pid, flags)

def pidfd_getfd(pidfd: int, target_fd: int, flags: int = GETFD_FLAGS) -> int:
    return libc.syscall(SYS_pidfd_getfd, pidfd, target_fd, flags)


class MessageDrain:
    def __init__(self, loop):
        self._queue = asyncio.Queue()
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


async def h264_processing(drain, frame_storage):
    import io
    import av
    raw_data = io.BytesIO()
    container = av.open(raw_data, format='h264', mode='r')

    while True:
        msg = await drain.get_latest()
        raw_data.write(msg.payload.to_bytes())
        raw_data.seek(0)
        for packet in container.demux():
            try:
                if packet.size == 0:
                    continue
                raw_data.seek(0)
                raw_data.truncate(0)
                for frame in packet.decode():
                    frame_array = frame.to_ndarray(format='rgb24')
                    frame_storage.set(frame_array.shape[1], frame_array.shape[0])
                    rr.log('/camera', rr.Image(frame_array))
            except Exception:
                continue


async def dma_processing(drain, frame_storage):
    from edgefirst.schemas.edgefirst_msgs import DmaBuffer
    import mmap

    while True:
        msg = await drain.get_latest()
        dma_buf = DmaBuffer.deserialize(msg.payload.to_bytes())
        pidfd = pidfd_open(dma_buf.pid)
        if pidfd < 0:
            return

        fd = pidfd_getfd(pidfd, dma_buf.fd, GETFD_FLAGS)
        if fd < 0:
            return

        frame_storage.set(dma_buf.width, dma_buf.height)
        # Now fd can be used as a file descriptor
        mm = mmap.mmap(fd, dma_buf.length)
        rr.log("/camera", rr.Image(bytes=mm[:], 
                                    width=dma_buf.width, 
                                    height=dma_buf.height, 
                                    pixel_format=rr.PixelFormat.YUY2))
        mm.close()
        os.close(fd)
        os.close(pidfd)


async def jpeg_processing(drain, frame_storage):
    import numpy as np
    import cv2
    from edgefirst.schemas.sensor_msgs import CompressedImage

    while True:
        msg = await drain.get_latest()
        image = CompressedImage.deserialize(msg.payload.to_bytes())
        np_arr = np.frombuffer(bytearray(image.data), np.uint8)
        im = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        im = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
        frame_storage.set(im.shape[0], im.shape[1])
        rr.log('/camera', rr.Image(im))


async def boxes2d_processing(drain, frame_storage):
    from edgefirst.schemas.edgefirst_msgs import Detect
    frame_size = await frame_storage.get()
    while True:
        msg = await drain.get_latest()
        frame_size = await frame_storage.get()
        centers, sizes, labels = [], [], []
        detection = Detect.deserialize(msg.payload.to_bytes())

        for box in detection.boxes:
            centers.append((int(box.center_x * frame_size[0]), int(box.center_y * frame_size[1])))
            sizes.append((int(box.width * frame_size[0]), int(box.height * frame_size[1])))
            labels.append(box.label)

        rr.log("/camera/boxes", rr.Boxes2D(centers=centers, sizes=sizes, labels=labels))
        rr.log("/metrics/detection_inference", rr.Scalars(float(detection.model_time.sec) + float(detection.model_time.nanosec / 1e9)))


async def mask_processing(drain, frame_storage, remote):
    import zstd
    import numpy as np
    from edgefirst.schemas.edgefirst_msgs import Mask
    frame_size = await frame_storage.get()
    rr.log("/", rr.AnnotationContext([(0, "background", (0, 0, 0, 0)), (1, "person", (0, 255, 0))]))
    while True:
        msg = await drain.get_latest()
        frame_size = await frame_storage.get()
        mask = Mask.deserialize(msg.payload.to_bytes())
        if remote:
            decoded_array = zstd.decompress(bytes(mask.mask))
            np_arr = np.frombuffer(decoded_array, np.uint8).reshape(mask.height, mask.width, -1)
        else:
            np_arr = np.asarray(mask.mask, dtype=np.uint8)
            np_arr = np.reshape(np_arr, [mask.height, mask.width, -1])
        # np_arr = cv2.resize(np_arr, frame_size)
        np_arr = np.argmax(np_arr, axis=2)

        rr.log("/camera/mask", rr.SegmentationImage(np_arr))


async def gps_processing(drain):
    from edgefirst.schemas.sensor_msgs import NavSatFix
    while True:
        msg = await drain.get_latest()
        gps = NavSatFix.deserialize(msg.payload.to_bytes())
        rr.log("/gps",
                rr.GeoPoints(lat_lon=[gps.latitude, gps.longitude]))


async def boxes3d_processing(drain):
    from edgefirst.schemas.edgefirst_msgs import Detect
    while True:
        msg = await drain.get_latest()
        detection = Detect.deserialize(msg.payload.to_bytes())

        # The 3D boxes are in an _optical frame of reference, where x is right, y is down, and z (distance) is forward
        # We will convert them to a normal frame of reference, where x is forward, y is left, and z is up
        centers = [(x.distance, -x.center_x, -x.center_y)
                    for x in detection.boxes]
        sizes = [(x.width, x.width, x.height)
                    for x in detection.boxes]

        rr.log("/pointcloud/fusion/boxes", rr.Boxes3D(centers=centers, sizes=sizes))


async def radar_processing(drain):
    from edgefirst.schemas.sensor_msgs import PointCloud2
    from edgefirst.schemas import decode_pcd, colormap, turbo_colormap
    while True:
        msg = await drain.get_latest()
        pcd = PointCloud2.deserialize(msg.payload.to_bytes())
        points = decode_pcd(pcd)
        clusters = [p for p in points if p.id > 0]
        max_id = max(p.id for p in clusters)
        pos = [[p.x, p.y, p.z] for p in clusters]
        colors = [colormap(turbo_colormap, p.id / max_id) for p in clusters]
        rr.log("/pointcloud/radar/clusters", rr.Points3D(pos, colors=colors))


async def lidar_processing(drain):
    from edgefirst.schemas.sensor_msgs import PointCloud2
    from edgefirst.schemas import decode_pcd, colormap, turbo_colormap
    while True:
        msg = await drain.get_latest()
        pcd = PointCloud2.deserialize(msg.payload.to_bytes())
        points = decode_pcd(pcd)
        clusters = [p for p in points if p.id > 0]
        max_id = max(p.id for p in clusters)
        pos = [[p.x, p.y, p.z] for p in clusters]
        colors = [colormap(turbo_colormap, p.id / max_id) for p in clusters]
        rr.log("/pointcloud/lidar/clusters", rr.Points3D(pos, colors=colors))


async def main_async(args):
    loop = asyncio.get_running_loop()

    # Setup rerun
    args.memory_limit = 10
    # Create the default Zenoh configuration and if the remote argument is
    # provided set the mode to client and add the target to the endpoints.
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    if args.remote is not None:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", '{"endpoints": ["%s"]}' % args.remote)
    session = zenoh.open(config)

    # Create a subscriber for all topics matching the pattern "rt/**"
    subscriber = session.declare_subscriber('rt/**')

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
        if 'rt/camera' in topic:
            if topic not in camera_topics:
                camera_topics.add(topic)
        elif 'rt/model' in topic:
            if topic not in model_topics:
                model_topics.add(topic)
        elif 'rt/radar' in topic:
            if topic not in radar_topics:
                radar_topics.add(topic)
        elif 'rt/fusion' in topic:
            if topic not in fusion_topics:
                fusion_topics.add(topic)
        elif 'rt/lidar' in topic:
            if topic not in lidar_topics:
                lidar_topics.add(topic)
        else:
            if topic not in misc_topics:
                misc_topics.add(topic)

    subscriber.undeclare()
    del subscriber

    args.memory_limit=10
    rr.script_setup(args, "mega_sample")
    blueprint = rrb.Blueprint(
        rrb.Grid(contents=[
            rrb.MapView(origin='/gps', name="GPS"),
            rrb.Spatial2DView(origin="/camera", name="Camera Feed"),
            rrb.Spatial3DView(origin="/pointcloud", name="Pointcloud Clusters"),
            rrb.TimeSeriesView(origin="/metrics", name="Model Information")
        ])
    )
    rr.send_blueprint(blueprint)

    async_funcs = []

    cam_drain = MessageDrain(loop)
    boxes2d_drain = MessageDrain(loop)
    mask_drain = MessageDrain(loop)
    radar_drain = MessageDrain(loop)
    lidar_drain = MessageDrain(loop)
    gps_drain = MessageDrain(loop)
    boxes3d_drain = MessageDrain(loop)

    frame_size_storage = FrameSize()

    cam_topic = None
    if args.remote is None and 'rt/camera/dma' in camera_topics:
        cam_topic = 'rt/camera/dma'
        cam_drain = MessageDrain(loop)
        session.declare_subscriber(cam_topic, cam_drain.callback)
        async_funcs.append(dma_processing(cam_drain, frame_size_storage))
    elif 'rt/camera/h264' in camera_topics:
        cam_topic = 'rt/camera/h264'
        cam_drain = MessageDrain(loop)
        session.declare_subscriber(cam_topic, cam_drain.callback)
        async_funcs.append(h264_processing(cam_drain, frame_size_storage))
    elif 'rt/camera/jpeg' in camera_topics:
        cam_topic = 'rt/camera/jpeg'
        cam_drain = MessageDrain(loop)
        session.declare_subscriber(cam_topic, cam_drain.callback)
        async_funcs.append(jpeg_processing(cam_drain, frame_size_storage))
    else:
        print("No camera topic available")

    if 'rt/model/boxes2d' in model_topics:
        boxes2d_drain = MessageDrain(loop)
        session.declare_subscriber('rt/model/boxes2d', boxes2d_drain.callback)
        async_funcs.append(boxes2d_processing(boxes2d_drain, frame_size_storage))

    if args.remote is None and 'rt/model/mask' in model_topics:
        session.declare_subscriber('rt/model/mask', mask_drain.callback)
    elif args.remote is not None and 'rt/model/mask_compressed' in model_topics:
        session.declare_subscriber('rt/model/mask_compressed', mask_drain.callback)
    elif 'rt/model/mask' in model_topics:
        session.declare_subscriber('rt/model/mask', mask_drain.callback)
    elif 'rt/model/mask_compressed' in model_topics:
        session.declare_subscriber('rt/model/mask_compressed', mask_drain.callback)

    if 'rt/model/mask' in model_topics or 'rt/model/mask_compressed' in model_topics:
        async_funcs.append(mask_processing(mask_drain, frame_size_storage, args.remote))

    # if 'rt/imu' in misc_topics:
    #     rr.log("/imu", rr.Boxes3D(half_sizes=[[0.5, 0.5, 0.5]], fill_mode="solid"))
    #     rr.log("/imu", rr.Transform3D(axis_length=2))
    #     imu_subscriber = session.declare_subscriber('rt/imu', imu_callback)

    if 'rt/gps' in misc_topics:
        session.declare_subscriber('rt/gps', gps_drain.callback)
        async_funcs.append(gps_processing(gps_drain))

    if 'rt/fusion/boxes3d' in fusion_topics:
        session.declare_subscriber('rt/fusion/boxes3d', boxes3d_drain.callback)
        async_funcs.append(boxes3d_processing(boxes3d_drain))

    if 'rt/radar/clusters' in radar_topics:
        session.declare_subscriber('rt/radar/clusters', radar_drain.callback)
        async_funcs.append(radar_processing(radar_drain))

    if 'rt/lidar/clusters' in lidar_topics:
        session.declare_subscriber('rt/lidar/clusters', lidar_drain.callback)
        async_funcs.append(lidar_processing(lidar_drain))

    # Launch concurrent processing tasks
    await asyncio.gather(*async_funcs)

    while True:
        time.sleep(0.01)

def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Mega Sample")
    parser.add_argument('-r', '--remote', type=str, default=None,
                        help="Connect to the remote endpoint instead of local.")
    rr.script_add_args(parser)
    args = parser.parse_args()

    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == "__main__":
    main()



    
