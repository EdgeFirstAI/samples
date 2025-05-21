import numpy as np
import rerun as rr
import zenoh

from argparse import ArgumentParser
from edgefirst.schemas.sensor_msgs import Image


if __name__ == "__main__":
    args = ArgumentParser(description="EdgeFirst Samples - LiDAR Reflect")
    args.add_argument('-r', '--remote', type=str, default=None,
                      help="Connect to the remote endpoint instead of local.")
    rr.script_add_args(args)
    args = args.parse_args()

    rr.script_setup(args, "lidar-reflect")

    # Create the default Zenoh configuration and if the remote argument is
    # provided set the mode to client and add the target to the endpoints.
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    if args.remote is not None:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", '{"endpoints": ["%s"]}' % args.remote)
    session = zenoh.open(config)

    # Create a subscriber for "rt/lidar/reflect"
    subscriber = session.declare_subscriber('rt/lidar/reflect')

    while True:
        msg = subscriber.recv()

        # Deserialize message
        reflect = Image.deserialize(msg.payload.to_bytes())

        # Process reflect image
        assert reflect.encoding == "mono8"

        data = np.array(reflect.data).reshape(
            (reflect.height, reflect.width)).astype(np.uint8)
        rr.log("lidar/depth", rr.Image(data))
