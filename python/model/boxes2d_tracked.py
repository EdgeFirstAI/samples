import zenoh
from edgefirst.schemas.edgefirst_msgs import Detect
from argparse import ArgumentParser
import sys
import rerun as rr
import asyncio
import time
import numpy as np
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

def boxes2d_worker(msg, boxes_tracked):
    detection = Detect.deserialize(msg.payload.to_bytes())
    centers = []
    sizes = []
    labels = []
    colors = []
    for box in detection.boxes:
        if box.track.id and box.track.id not in boxes_tracked:
            boxes_tracked[box.track.id] = [box.label + ": " + box.track.id[:6], list(np.random.choice(range(256), size=3))]
        if box.track.id:
            colors.append(boxes_tracked[box.track.id][1])
            labels.append(boxes_tracked[box.track.id][0])
        else:
            colors.append([0,255,0])
            labels.append(box.label)
        centers.append((box.center_x, box.center_y))
        sizes.append((box.width, box.height))
    rr.log("boxes", rr.Boxes2D(centers=centers, sizes=sizes, labels=labels, colors=colors))

async def boxes2d_handler(drain):
    boxes_tracked = {}
    while True:
        msg = await drain.get_latest()

        thread = threading.Thread(target=boxes2d_worker, args=[msg, boxes_tracked])
        thread.start()
        
        while thread.is_alive():
            await asyncio.sleep(0.001)
        thread.join()
    
async def main_async(args):
    # Setup rerun
    args.memory_limit = 10
    rr.script_setup(args, "model-boxes2d")

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

    session.declare_subscriber('rt/model/boxes2d', drain.callback)
    await asyncio.gather((boxes2d_handler(drain)))

    while True:
        asyncio.sleep(0.001)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Boxes2D Tracked")
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
