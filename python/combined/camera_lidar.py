from argparse import ArgumentParser
import asyncio
import io
import sys
import av
import zenoh
import rerun as rr
import rerun.blueprint as rrb
from edgefirst.schemas.edgefirst_msgs import Detect
from edgefirst.schemas.sensor_msgs import PointCloud2
from edgefirst.schemas import decode_pcd, colormap, turbo_colormap


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
                    frame_storage.set(
                        frame_array.shape[1], frame_array.shape[0])
                    rr.log('/camera', rr.Image(frame_array))
            except Exception:
                continue


async def boxes2d_processing(drain, frame_storage):
    frame_size = await frame_storage.get()
    while True:
        msg = await drain.get_latest()
        frame_size = await frame_storage.get()
        centers, sizes, labels = [], [], []
        detection = Detect.deserialize(msg.payload.to_bytes())

        for box in detection.boxes:
            centers.append(
                (int(box.center_x * frame_size[0]), int(box.center_y * frame_size[1])))
            sizes.append(
                (int(box.width * frame_size[0]), int(box.height * frame_size[1])))
            labels.append(box.label)

        rr.log("/camera/boxes", rr.Boxes2D(centers=centers,
               sizes=sizes, labels=labels))


async def lidar_processing(drain):
    while True:
        msg = await drain.get_latest()
        pcd = PointCloud2.deserialize(msg.payload.to_bytes())
        points = decode_pcd(pcd)
        clusters = [p for p in points if p.cluster_id > 0]
        max_id = max(p.cluster_id for p in clusters)
        pos = [[p.x, p.y, p.z] for p in clusters]
        colors = [colormap(turbo_colormap, p.cluster_id / max_id)
                  for p in clusters]
        rr.log("/pointcloud/lidar/clusters", rr.Points3D(pos, colors=colors))


async def main_async(args):
    loop = asyncio.get_running_loop()

    # Setup rerun
    args.memory_limit = 10
    rr.script_setup(args, "camera_lidar")

    blueprint = rrb.Blueprint(
        rrb.Grid(contents=[
            rrb.Spatial2DView(origin="/camera", name="Camera Feed"),
            rrb.Spatial3DView(origin="/pointcloud", name="Pointcloud Clusters")
        ])
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
    h264_drain = MessageDrain(loop)
    boxes2d_drain = MessageDrain(loop)
    lidar_drain = MessageDrain(loop)

    frame_size_storage = FrameSize()

    # Declare subscribers
    session.declare_subscriber('rt/camera/h264', h264_drain.callback)
    session.declare_subscriber('rt/model/boxes2d', boxes2d_drain.callback)
    session.declare_subscriber('rt/lidar/clusters', lidar_drain.callback)

    # Launch concurrent processing tasks
    await asyncio.gather(
        h264_processing(h264_drain, frame_size_storage),
        boxes2d_processing(boxes2d_drain, frame_size_storage),
        lidar_processing(lidar_drain),
    )


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Camera Lidar")
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
