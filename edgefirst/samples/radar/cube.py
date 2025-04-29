import zenoh
from edgefirst.schemas.edgefirst_msgs import RadarCube
from argparse import ArgumentParser
from time import time
import rerun as rr
import numpy as np
import math

FACTOR = 65535.0 / 2500.0

if __name__ == "__main__":
    args = ArgumentParser(description="EdgeFirst Samples - RadarInfo")
    args.add_argument('-c', '--connect', type=str, default=None,
                      help="Connect to a Zenoh router rather than peer mode.")
    args.add_argument('-t', '--time', type=float, default=None,
                      help="Time in seconds to run command before exiting.")
    args.add_argument('-r', '--rerun', type=str, default=None,
                      help="Rerun file.")
    args = args.parse_args()

    rr.init("radar/cube")
    rr.save("radar-cube.rrd")

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

        data = np.array(radar_cube.cube).reshape(radar_cube.shape)
        data = np.minimum(
            np.log2(np.abs(data.astype(np.float64)) + 1)*FACTOR, 65535).astype(np.uint16)
        rr.log("radar/cube", rr.Tensor(data,
               dim_names=["SEQ", "RANGE", "RX", "DOPPLER"]))
