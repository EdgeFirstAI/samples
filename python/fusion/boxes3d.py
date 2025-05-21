import zenoh
from edgefirst.schemas.edgefirst_msgs import Detect
from argparse import ArgumentParser
import sys
import rerun as rr


def main():
    args = ArgumentParser(description="EdgeFirst Samples - Boxes3D")
    args.add_argument('-r', '--remote', type=str, default=None,
                      help="Connect to a Zenoh router rather than local.")
    args.add_argument('-t', '--timeout', type=float, default=None,
                      help="Time in seconds to run command before exiting.")
    rr.script_add_args(args)
    args = args.parse_args()

    rr.script_setup(args, "fusion/boxes3d Example")

    # Create the default Zenoh configuration and if the connect argument is
    # provided set the mode to client and add the target to the endpoints.
    config = zenoh.Config()
    if args.remote is not None:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", '{"endpoints": ["%s"]}' % args.remote)
    session = zenoh.open(config)

    # Create a subscriber for "rt/fusion/boxes3d"
    subscriber = session.declare_subscriber('rt/fusion/boxes3d')

    while True:
        msg = subscriber.recv()
        detection = Detect.deserialize(msg.payload.to_bytes())
        print(f"Recieved {len(detection.boxes)} 3D boxes.")

        # The 3D boxes are in an _optical frame of reference, where x is right, y is down, and z (distance) is forward
        # We will convert them to a normal frame of reference, where x is forward, y is left, and z is up
        centers = [(x.distance, -x.center_x, -x.center_y)
                   for x in detection.boxes]
        sizes = [(x.width, x.width, x.height)
                 for x in detection.boxes]

        rr.log("fusion/boxes3d", rr.Boxes3D(centers=centers, sizes=sizes))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
