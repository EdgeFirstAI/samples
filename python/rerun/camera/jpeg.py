import zenoh
from edgefirst.schemas.sensor_msgs import CompressedImage
import rerun as rr
from argparse import ArgumentParser
import numpy as np
import sys
import cv2
import asyncio
import zenoh
import time
import threading
import rerun.blueprint as rrb

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

def jpeg_worker(msg):
    image = CompressedImage.deserialize(msg.payload.to_bytes())
    np_arr = np.frombuffer(bytearray(image.data), np.uint8)
    im = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    im = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
    rr.log('/camera', rr.Image(im))

    
async def jpeg_handler(drain):
    while True:
        msg = await drain.get_latest()
        thread = threading.Thread(target=jpeg_worker, args=[msg])
        thread.start()
        
        while thread.is_alive():
            await asyncio.sleep(0.001)
        thread.join()


async def main_async(args):
    # Setup rerun
    args.memory_limit = 10
    rr.script_setup(args, "camera-jpeg")
    blueprint = rrb.Blueprint(
        rrb.Grid(contents=[
            rrb.Spatial2DView(origin="/camera", name="Camera Feed")
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
    loop = asyncio.get_running_loop()
    drain = MessageDrain(loop)

    session.declare_subscriber('rt/camera/jpeg', drain.callback)
    await asyncio.gather((jpeg_handler(drain)))

    while True:
        asyncio.sleep(0.001)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - JPEG")
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