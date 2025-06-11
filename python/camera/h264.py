from argparse import ArgumentParser
import asyncio
import io
import sys
import av
import zenoh
import time
import rerun as rr
import rerun.blueprint as rrb

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


async def h264_processing(drain):
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
                    rr.log('/camera', rr.Image(frame_array))
            except Exception:
                continue
    
async def main_async(args):
    # Setup rerun
    args.memory_limit = 10
    rr.script_setup(args, "h264")

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
    h264_drain = MessageDrain(loop)

    session.declare_subscriber('rt/camera/h264', h264_drain.callback)
    await asyncio.gather((h264_processing(h264_drain)))

    while True:
        time.sleep(0.001)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - H264")
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

