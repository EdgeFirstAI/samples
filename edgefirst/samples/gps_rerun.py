import atexit
import sys
import zenoh
from time import time
from argparse import ArgumentParser
from edgefirst.schemas.sensor_msgs import NavSatFix
import rerun as rr

if __name__ == "__main__":
    args = ArgumentParser(description="EdgeFirst Samples - GPS")
    args.add_argument('-c', '--connect', type=str, default=None,
                      help="Connect to a Zenoh router rather than peer mode.")
    args.add_argument('-t', '--time', type=float, default=None,
                      help="Time in seconds to run command before exiting.")
    args = args.parse_args()

    rr.init("GPS Example", spawn=True)
    # rr.serve_web_viewer(open_browser=False, web_port=4321)

    # Create the default Zenoh configuration and if the connect argument is
    # provided set the mode to client and add the target to the endpoints.
    config = zenoh.Config()
    if args.connect is not None:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", '{"endpoints": ["%s"]}' % args.connect)
    session = zenoh.open(config)

    # Create a subscriber for "rt/imu"
    subscriber = session.declare_subscriber('rt/gps')

    # Keep a list of discovered topics to avoid noise from duplicates
    start = time()

    while True:
        if args.time is not None and time() - start >= args.time:
            break
        msg = subscriber.recv()

        # deserialize message
        gps = NavSatFix.deserialize(msg.payload.to_bytes())
        lat = gps.latitude
        long = gps.longitude
        print("Latitude: %.6f Longitude: %.6f" % (lat, long))
        rr.log("CurrentLoc", rr.GeoPoints(lat_lon=[lat, long]))
