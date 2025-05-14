import zenoh
from edgefirst.schemas.sensor_msgs import PointCloud2
from edgefirst.schemas import decode_pcd, colormap, turbo_colormap
from argparse import ArgumentParser
import sys
import rerun as rr


def main():
    args = ArgumentParser(description="EdgeFirst Samples - Radar")
    args.add_argument('-r', '--remote', type=str, default=None,
                      help="Connect to a Zenoh router rather than local.")
    args.add_argument('-t', '--timeout', type=float, default=None,
                      help="Time in seconds to run command before exiting.")
    rr.script_add_args(args)
    args = args.parse_args()

    rr.script_setup(args, "fusion/radar Example")

    # Create the default Zenoh configuration and if the connect argument is
    # provided set the mode to client and add the target to the endpoints.
    config = zenoh.Config()
    if args.remote is not None:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", '{"endpoints": ["%s"]}' % args.remote)
    session = zenoh.open(config)

    # Create a subscriber for "rt/fusion/radar"
    subscriber = session.declare_subscriber('rt/fusion/radar')

    while True:
        msg = subscriber.recv()

        pcd = PointCloud2.deserialize(msg.payload.to_bytes())
        points = decode_pcd(pcd)
        max_class = max(max([p.fields["vision_class"] for p in points]), 1)
        pos = [[p.x, p.y, p.z] for p in points]
        colors = [
            colormap(turbo_colormap, p.fields["vision_class"]/max_class) for p in points]
        rr.log("fusion/radar", rr.Points3D(positions=pos, colors=colors))

        points = [p for p in points if p.fields["vision_class"] != 0]

        min_x = min([p.x for p in points], default=float("inf"))
        max_x = max([p.x for p in points], default=float("-inf"))

        min_y = min([p.y for p in points], default=float("inf"))
        max_y = max([p.y for p in points], default=float("-inf"))

        min_z = min([p.z for p in points], default=float("inf"))
        max_z = max([p.z for p in points], default=float("-inf"))
        print(
            f"Recieved {len(points)} radar points with non-background vision_class. Values: x: [{min_x:.2f}, {max_x:.2f}]\ty: [{min_y:.2f}, {max_y:.2f}]\tz: [{min_z:.2f}, {max_z:.2f}]")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
