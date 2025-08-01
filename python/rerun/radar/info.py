import zenoh
import sys
import asyncio
import time
from argparse import ArgumentParser
from edgefirst.schemas.edgefirst_msgs import RadarInfo
import rerun as rr
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


def info_worker(msg):
    radar_info = RadarInfo.deserialize(msg.payload.to_bytes())
    radar_log = "Range Mode: %s\n" % str(radar_info.frequency_sweep)
    radar_log += "Center Band: %s\n" % str(radar_info.center_frequency)
    radar_log += "Sensitivity: %s\n" % str(radar_info.detection_sensitivity)
    radar_log += "Range Toggle: %s\n" % str(radar_info.range_toggle)
    rr.log("RadarInfo", rr.TextLog(radar_log))


async def info_handler(drain):
    while True:
        msg = await drain.get_latest()
        thread = threading.Thread(target=info_worker, args=[msg])
        thread.start()
        
        while thread.is_alive():
            await asyncio.sleep(0.001)
        thread.join()


async def main_async(args):
    # Setup rerun
    args.memory_limit = 10
    rr.script_setup(args, "radar/info")

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

    session.declare_subscriber('rt/radar/info', drain.callback)
    await asyncio.gather((info_handler(drain)))

    while True:
        asyncio.sleep(0.001)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Radar Info")
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
