import zenoh
from edgefirst.schemas.edgefirst_msgs import RadarCube
from argparse import ArgumentParser
from time import time
import rerun

if __name__ == "__main__":
    args = ArgumentParser(description="EdgeFirst Samples - RadarInfo")
    args.add_argument('-c', '--connect', type=str, default=None,
                      help="Connect to a Zenoh router rather than peer mode.")
    args.add_argument('-t', '--time', type=float, default=None,
                      help="Time in seconds to run command before exiting.")
    args = args.parse_args()

    # Create the default Zenoh configuration and if the connect argument is
    # provided set the mode to client and add the target to the endpoints.
    config = zenoh.Config()
    if args.connect is not None:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", '{"endpoints": ["%s"]}' % args.connect)
    session = zenoh.open(config)

    # Create a subscriber for "rt/radar/info"
    subscriber = session.declare_subscriber('rt/radar/cube')

    start = time()

    while True:
        if args.time is not None and time() - start >= args.time:
            break
        msg = subscriber.recv()

        # deserialize message
        radar_cube = RadarCube.deserialize(msg.payload.to_bytes())
        print(
            f"The radar cube has shape {radar_cube.shape}")
