import zenoh
from edgefirst.schemas.edgefirst_msgs import RadarInfo
from argparse import ArgumentParser
from time import time
import rerun as rr

if __name__ == "__main__":
    args = ArgumentParser(description="EdgeFirst Samples - RadarInfo")
    args.add_argument('-c', '--connect', type=str, default=None,
                      help="Connect to a Zenoh router rather than peer mode.")
    args.add_argument('-t', '--time', type=float, default=None,
                      help="Time in seconds to run command before exiting.")
    args.add_argument('-r', '--rerun', type=str, default=None,
                      help="Rerun file.")
    args = args.parse_args()

    rr.init("radar/info")
    rr.save("radar-info.rrd")

    # Create the default Zenoh configuration and if the connect argument is
    # provided set the mode to client and add the target to the endpoints.
    config = zenoh.Config()
    if args.connect is not None:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", '{"endpoints": ["%s"]}' % args.connect)
    session = zenoh.open(config)

    # Create a subscriber for "rt/radar/info"
    subscriber = session.declare_subscriber('rt/radar/info')

    start = time()

    while True:
        if args.time is not None and time() - start >= args.time:
            break
        msg = subscriber.recv()

        # deserialize message
        radar_info = RadarInfo.deserialize(msg.payload.to_bytes())
        print(
            f"The radar configuration is: center frequency: {radar_info.center_frequency}   frequency sweep: {radar_info.frequency_sweep}   range toggle: {radar_info.range_toggle}   detection sensitivity: {radar_info.detection_sensitivity}   sending cube: {radar_info.cube}")

        rr.log("radar/info", rr.TextLog(
            f"The radar configuration is: center frequency: {radar_info.center_frequency}   frequency sweep: {radar_info.frequency_sweep}   range toggle: {radar_info.range_toggle}   detection sensitivity: {radar_info.detection_sensitivity}   sending cube: {radar_info.cube}", level="INFO"))
