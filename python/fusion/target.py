import zenoh
from edgefirst.schemas.sensor_msgs import PointCloud2
from argparse import ArgumentParser
import time
import atexit
import sys


def handler(sample):
    # Deserialize message
    target = PointCloud2.deserialize(sample.payload.to_bytes())
    print(f"Received message: {target}")


def main():
    args = ArgumentParser(description="EdgeFirst Samples - Target")
    args.add_argument('-c', '--connect', type=str, default=None,
                      help="Connect to a Zenoh router rather than peer mode.")
    args.add_argument('-t', '--timeout', type=float, default=None,
                      help="Time in seconds to run command before exiting.")
    args = args.parse_args()

    # Create the default Zenoh configuration and if the connect argument is
    # provided set the mode to client and add the target to the endpoints.
    config = zenoh.Config()
    if args.connect is not None:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", '{"endpoints": ["%s"]}' % args.connect)
    session = zenoh.open(config)

    # Create a subscriber for "rt/fusion/targets"
    subscriber = session.declare_subscriber('rt/fusion/targets', handler)

    def _on_exit():
        session.close()
    atexit.register(_on_exit)

    # The declare_subscriber runs asynchronously, so we need to block the main
    # thread to keep the program running.  We use time.sleep() to do this
    # but an application could have its main control loop here instead.
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nExiting...")
        session.close()
        sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
