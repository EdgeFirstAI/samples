import zenoh
from edgefirst.schemas.sensor_msgs import Image
from argparse import ArgumentParser
from time import time
import rerun

if __name__ == "__main__":
    args = ArgumentParser(description="EdgeFirst Samples - Lidar reflect")
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

    # Create a subscriber for "rt/lidar/reflect"
    subscriber = session.declare_subscriber('rt/lidar/reflect')

    start = time()

    while True:
        if args.time is not None and time() - start >= args.time:
            break
        msg = subscriber.recv()

        # Deserialize message
        reflect = Image.deserialize(msg.payload.to_bytes())

        # Process reflect image
        assert reflect.encoding == "mono8"
        reflect_vals = reflect.data

        min_reflect_mm = min(reflect_vals)
        max_reflect_mm = max(reflect_vals)
        print(
            f"Recieved {reflect.width}x{reflect.height} reflect image. reflect: [{min_reflect_mm}, {max_reflect_mm}]",
        )
