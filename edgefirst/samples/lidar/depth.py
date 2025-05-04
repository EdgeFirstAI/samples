import numpy as np
import rerun as rr
import struct
import zenoh

from argparse import ArgumentParser
from edgefirst.schemas.sensor_msgs import Image


if __name__ == "__main__":
    args = ArgumentParser(description="EdgeFirst Samples - LiDAR Depth")
    args.add_argument('-r', '--remote', type=str, default=None,
                      help="Connect to the remote endpoint instead of local.")
    rr.script_add_args(args)
    args = args.parse_args()

    rr.script_setup(args, "lidar-depth")

    # Create the default Zenoh configuration and if the remote argument is
    # provided set the mode to client and add the target to the endpoints.
    config = zenoh.Config()
    if args.remote is not None:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", '{"endpoints": ["%s"]}' % args.remote)
    session = zenoh.open(config)

    # Create a subscriber for "rt/lidar/depth"
    subscriber = session.declare_subscriber('rt/lidar/depth')

    while True:
        msg = subscriber.recv()

        # Deserialize message
        depth = Image.deserialize(msg.payload.to_bytes())

        # Process depth image
        assert depth.encoding == "mono16"
        endian_format = ">" if depth.is_bigendian else "<"
        depth_vals = list(struct.unpack(
            f"{endian_format}{depth.width*depth.height}H", bytes(depth.data)))
        data = (np.array(depth_vals).reshape(
            (depth.height, depth.width)) / 255).astype(np.uint8)
        rr.log("lidar/depth", rr.Image(data))
