import foxglove
from foxglove.schemas import Timestamp, CompressedVideo
from argparse import ArgumentParser
from edgefirst.schemas.foxglove_msgs import CompressedVideo as efcv
import asyncio
import sys
import zenoh
import threading

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

def h264_worker(msg):
    vid = efcv.deserialize(msg.payload.to_bytes())
    foxglove.log(
        "/camera",
        CompressedVideo(
            timestamp=Timestamp(vid.timestamp.sec, vid.timestamp.nanosec),
            frame_id=vid.frame_id,
            data= bytes(vid.data),
            format = vid.format
        )
    )
    
async def h264_handler(drain):
    while True:
        msg = await drain.get_latest()
        thread = threading.Thread(target=h264_worker, args=[msg])
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

    session.declare_subscriber('rt/camera/h264', drain.callback)
    await asyncio.gather((h264_handler(drain)))

    while True:
        asyncio.sleep(0.001)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - H264")
    parser.add_argument('-r', '--remote', type=str, default=None,
                        help="Connect to the remote endpoint instead of local.")
    args = parser.parse_args()

    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == "__main__":
    main()