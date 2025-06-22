import rerun as rr
import zenoh
from argparse import ArgumentParser
from edgefirst.schemas import turbo_colormap, colormap, decode_pcd
from edgefirst.schemas.sensor_msgs import PointCloud2
import asyncio
import time
import sys
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


def clusters_worker(msg):
    pcd = PointCloud2.deserialize(msg.payload.to_bytes())
    points = decode_pcd(pcd)
    clusters = [p for p in points if p.cluster_id > 0]
    if not clusters:
        rr.log("lidar/clusters", rr.Points3D([], colors=[]))  
        return
    max_id = max(p.cluster_id for p in clusters)
    pos = [[p.x, p.y, p.z] for p in clusters]
    colors = [colormap(turbo_colormap, p.cluster_id / max_id)
            for p in clusters]
    rr.log("lidar/clusters", rr.Points3D(pos, colors=colors))


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
    args.memory_limit = 10
    rr.script_setup(args, "lidar/clusters")

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

    session.declare_subscriber('rt/lidar/clusters', drain.callback)
    await asyncio.gather((clusters_handler(drain)))

    while True:
        time.sleep(0.001)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Lidar Clusters")
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
