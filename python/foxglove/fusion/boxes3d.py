import zenoh
from edgefirst.schemas.edgefirst_msgs import Detect
from argparse import ArgumentParser
import sys
import asyncio
import threading
import foxglove
from foxglove.schemas import (
    CubePrimitive, Pose, Quaternion, Vector3, 
    SceneEntity, SceneEntityDeletion, SceneEntityDeletionType, 
    SceneUpdate, Timestamp
)

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


def boxes3d_worker(msg):
    detection = Detect.deserialize(msg.payload.to_bytes())
    # The 3D boxes are in an _optical frame of reference, where x is right, y is down, and z (distance) is forward
    # We will convert them to a normal frame of reference, where x is forward, y is left, and z is up

    ts = Timestamp(sec=detection.header.stamp.sec, nsec=detection.header.stamp.nanosec)
    cube_list = []
    for box in detection.boxes:
        print(box)
        cube = CubePrimitive(
            pose=Pose(position=Vector3(x=box.distance, y=-box.center_x, z=-box.center_y),
                      orientation=Quaternion(x=0, y=0, z=0, w=1)),
            size=Vector3(x=box.width, y=box.width, z=box.height)
        )
        cube_list.append(cube)
    print(len(cube_list))
    entity = SceneEntity(timestamp=ts, frame_id=detection.header.frame_id,
                         id="boxes3d", cubes=cube_list)

    foxglove.log("/fusion/boxes3d",
        SceneUpdate(
            deletions=[SceneEntityDeletion(timestamp=ts, type=SceneEntityDeletionType.All)],
            entities=[entity]
        )
    )


async def boxes3d_handler(drain):
    while True:
        msg = await drain.get_latest()
        thread = threading.Thread(target=boxes3d_worker, args=[msg])
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

    session.declare_subscriber('rt/fusion/boxes3d', drain.callback)
    await asyncio.gather((boxes3d_handler(drain)))

    while True:
        asyncio.sleep(0.001)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Boxes3D")
    parser.add_argument('-r', '--remote', type=str, default=None,
                        help="Connect to the remote endpoint instead of local.")
    args = parser.parse_args()

    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == "__main__":
    main()
