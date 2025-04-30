import zenoh
from edgefirst.schemas.sensor_msgs import Image
import struct
from argparse import ArgumentParser
from time import time
import rerun as rr
import numpy as np

if __name__ == "__main__":
    args = ArgumentParser(description="EdgeFirst Samples - Lidar Depth")
    args.add_argument('-c', '--connect', type=str, default=None,
                      help="Connect to a Zenoh router rather than peer mode.")
    args.add_argument('-t', '--time', type=float, default=None,
                      help="Time in seconds to run command before exiting.")
    args.add_argument('-r', '--rerun', type=str, default=None,
                      help="Rerun file.")
    args = args.parse_args()

    rr.init("lidar/depth")
    rr.save("lidar-depth.rrd")

    # Create the default Zenoh configuration and if the connect argument is
    # provided set the mode to client and add the target to the endpoints.
    config = zenoh.Config()
    if args.connect is not None:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", '{"endpoints": ["%s"]}' % args.connect)
    session = zenoh.open(config)

    # Create a subscriber for "rt/lidar/depth"
    subscriber = session.declare_subscriber('rt/lidar/depth')
    
    start = time()

    while True:
        if args.time is not None and time() - start >= args.time:
            break
        msg = subscriber.recv()

        # Deserialize message
        depth = Image.deserialize(msg.payload.to_bytes())

        # Process depth image
        assert depth.encoding == "mono16"
        endian_format = ">" if depth.is_bigendian else "<"
        depth_vals = list(struct.unpack(
            f"{endian_format}{depth.width*depth.height}H", bytes(depth.data)))
        min_depth_mm = min(depth_vals)
        max_depth_mm = max(depth_vals)
        print(
            f"Recieved {depth.width}x{depth.height} depth image. Depth: [{min_depth_mm}, {max_depth_mm}]",
        )
        data = (np.array(depth_vals).reshape((depth.height, depth.width)) / 255).astype(np.uint8)
        rr.log("lidar/depth", rr.Image(data))
