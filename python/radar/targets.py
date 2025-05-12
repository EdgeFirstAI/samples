import rerun as rr
import zenoh

from argparse import ArgumentParser
from edgefirst.schemas import decode_pcd
from edgefirst.schemas.sensor_msgs import PointCloud2


if __name__ == "__main__":
    args = ArgumentParser(description="EdgeFirst Samples - Lidar Points")
    args.add_argument('-r', '--remote', type=str, default=None,
                      help="Connect to the remote endpoint instead of local.")
    rr.script_add_args(args)
    args = args.parse_args()

    rr.script_setup(args, "radar-targets")

    # Create the default Zenoh configuration and if the remote argument is
    # provided set the mode to client and add the target to the endpoints.
    config = zenoh.Config()
    if args.remote is not None:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", '{"endpoints": ["%s"]}' % args.remote)
    session = zenoh.open(config)

    # Create a subscriber for "rt/radar/targets"
    subscriber = session.declare_subscriber('rt/radar/targets')

    while True:
        msg = subscriber.recv()

        pcd = PointCloud2.deserialize(msg.payload.to_bytes())
        points = decode_pcd(pcd)

        pos = [[p.x, p.y, p.z] for p in points]
        rr.log("radar/targets", rr.Points3D(pos))
