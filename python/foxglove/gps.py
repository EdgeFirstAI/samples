import zenoh
import sys
import asyncio
from argparse import ArgumentParser
from edgefirst.schemas.sensor_msgs import NavSatFix
import threading
import foxglove
from foxglove.schemas import Timestamp, LocationFix, LocationFixPositionCovarianceType

type_map = {
    0: LocationFixPositionCovarianceType.Unknown,
    1: LocationFixPositionCovarianceType.Approximated,
    2: LocationFixPositionCovarianceType.DiagonalKnown,
    3: LocationFixPositionCovarianceType.Known
}

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


def gps_worker(msg):
    gps = NavSatFix.deserialize(msg.payload.to_bytes())
    ts = Timestamp(sec=gps.header.stamp.sec, nsec=gps.header.stamp.nanosec)
    foxglove.log("/gps", LocationFix(timestamp=ts, frame_id=gps.header.frame_id,
                                     latitude=gps.latitude, longitude=gps.longitude,
                                     altitude=gps.altitude, position_covariance=gps.position_covariance,
                                     position_covariance_type=type_map[gps.position_covariance_type]))


async def gps_handler(drain):
    while True:
        msg = await drain.get_latest()
        thread = threading.Thread(target=gps_worker, args=[msg])
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

    session.declare_subscriber('rt/gps', drain.callback)
    await asyncio.gather((gps_handler(drain)))

    while True:
        asyncio.sleep(0.001)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - GPS")
    parser.add_argument('-r', '--remote', type=str, default=None,
                        help="Connect to the remote endpoint instead of local.")
    args = parser.parse_args()

    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == "__main__":
    main()
