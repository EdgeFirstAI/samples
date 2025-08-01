import zenoh
from argparse import ArgumentParser
from edgefirst.schemas import turbo_colormap, colormap, decode_pcd
from edgefirst.schemas.sensor_msgs import PointCloud2
from edgefirst.schemas.geometry_msgs import TransformStamped
import asyncio
import sys
import threading
import struct
import foxglove
from foxglove.schemas import PointCloud, Pose, Quaternion, Vector3, PackedElementField, PackedElementFieldNumericType

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


def clusters_worker(msg):
    pcd = PointCloud2.deserialize(msg.payload.to_bytes())
    points = decode_pcd(pcd)
    clusters = [p for p in points if p.cluster_id > 0]
    if not clusters:
        return
    
    max_id = max(p.cluster_id for p in clusters)
    point_struct = struct.Struct("<fffffff")
    buffer = bytearray(point_struct.size * len(clusters))

    for i, p in enumerate(clusters):
        color = colormap(turbo_colormap, p.cluster_id / max_id)
        point_struct.pack_into(buffer, i * point_struct.size, p.x, p.y, p.z, 
                               color[0], color[1], 
                               color[2], 1.0)

    pc = PointCloud(
        frame_id="points",
        pose=Pose(
            position=Vector3(x=0, y=0, z=-0.19),
            orientation=Quaternion(x=0, y=0, z=-0.9998157, w=0.0191974),
        ),
        point_stride=28,  # 4 fields * 4 bytes
        fields=[
            PackedElementField(name="x", offset=0, type=PackedElementFieldNumericType.Float32),
            PackedElementField(name="y", offset=4, type=PackedElementFieldNumericType.Float32),
            PackedElementField(name="z", offset=8, type=PackedElementFieldNumericType.Float32),
            PackedElementField(name="rgba", offset=12, type=PackedElementFieldNumericType.Float32),
        ],
        data=bytes(buffer),
    )
    foxglove.log("lidar/clusters", pc)


async def clusters_handler(drain):
    while True:
        msg = await drain.get_latest()
        thread = threading.Thread(target=clusters_worker, args=[msg])
        thread.start()
        
        while thread.is_alive():
            await asyncio.sleep(0.001)
        thread.join()


def static_worker(msg):
    static = TransformStamped.deserialize(msg.payload.to_bytes())
    print(static)


async def static_handler(drain):
    while True:
        msg = await drain.get_latest()
        thread = threading.Thread(target=static_worker, args=[msg])
        thread.start()
        
        while thread.is_alive():
            await asyncio.sleep(0.001)
        thread.join()



async def main_async(args):
    _ = foxglove.start_server()

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
    static_drain = MessageDrain(loop)

    session.declare_subscriber('rt/lidar/clusters', drain.callback)
    session.declare_subscriber('rt/tf_static', static_drain.callback)
    await asyncio.gather(clusters_handler(drain), static_handler(static_drain))

    while True:
        asyncio.sleep(0.001)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Lidar Clusters")
    parser.add_argument('-r', '--remote', type=str, default=None,
                        help="Connect to the remote endpoint instead of local.")
    args = parser.parse_args()

    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == "__main__":
    main()
