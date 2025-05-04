from argparse import ArgumentParser

import numpy as np
import rerun as rr
import zenoh
from edgefirst.schemas.edgefirst_msgs import RadarCube

if __name__ == "__main__":
    args = ArgumentParser(description="EdgeFirst Samples - Radar Cube")
    args.add_argument('-r', '--remote', type=str, default=None,
                      help="Connect to the remote endpoint instead of local.")
    rr.script_add_args(args)
    args = args.parse_args()

    rr.script_setup(args, "radar-cube")

    # Create the default Zenoh configuration and if the remote argument is
    # provided set the mode to client and add the target to the endpoints.
    config = zenoh.Config()
    if args.remote is not None:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", '{"endpoints": ["%s"]}' % args.remote)
    session = zenoh.open(config)

    # Create a subscriber for "rt/radar/info"
    subscriber = session.declare_subscriber('rt/radar/cube')

    while True:
        msg = subscriber.recv()

        # deserialize message
        radar_cube = RadarCube.deserialize(msg.payload.to_bytes())
        print(
            f"The radar cube has shape {radar_cube.shape}")

        data = np.array(radar_cube.cube).reshape(radar_cube.shape)
        # Take the absolute value of the data to improve visualization.
        data = np.abs(data)
        rr.log("radar/cube",
               rr.Tensor(data, dim_names=["SEQ", "RANGE", "RX", "DOPPLER"]))
