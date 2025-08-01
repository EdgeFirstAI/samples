import rerun as rr
import zenoh
import sys
import asyncio
import struct
from argparse import ArgumentParser
from edgefirst.schemas import decode_pcd
from edgefirst.schemas.sensor_msgs import PointCloud2
import threading
import foxglove
from foxglove.schemas import PointCloud, Pose, Vector3, Quaternion, PackedElementField, PackedElementFieldNumericType

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


def targets_worker(msg):
    pcd = PointCloud2.deserialize(msg.payload.to_bytes())
    points = decode_pcd(pcd)

    point_struct = struct.Struct("<fff")
    buffer = bytearray(point_struct.size * len(points))

    for i, p in enumerate(points):
        point_struct.pack_into(buffer, i * point_struct.size, p.x, p.y, p.z)

    pc = PointCloud(
        frame_id="points",
        pose=Pose(
            position=Vector3(x=0, y=0, z=0),
            orientation=Quaternion(x=0, y=0, z=0, w=1),
        ),
        point_stride=12,  # 4 fields * 4 bytes
        fields=[
            PackedElementField(name="x", offset=0, type=PackedElementFieldNumericType.Float32),
            PackedElementField(name="y", offset=4, type=PackedElementFieldNumericType.Float32),
            PackedElementField(name="z", offset=8, type=PackedElementFieldNumericType.Float32),
        ],
        data=bytes(buffer),
    )
    foxglove.log("radar/targets", pc)


async def targets_handler(drain):
    while True:
        msg = await drain.get_latest()
        thread = threading.Thread(target=targets_worker, args=[msg])
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

    session.declare_subscriber('rt/radar/targets', drain.callback)
    await asyncio.gather((targets_handler(drain)))

    while True:
        asyncio.sleep(0.001)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Radar Targets")
    parser.add_argument('-r', '--remote', type=str, default=None,
                        help="Connect to the remote endpoint instead of local.")
    args = parser.parse_args()

    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == "__main__":
    main()
