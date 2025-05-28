import rerun as rr
import zenoh

from argparse import ArgumentParser
from edgefirst.schemas.sensor_msgs import PointCloud2
from edgefirst.schemas import turbo_colormap, colormap, decode_pcd


if __name__ == "__main__":
    args = ArgumentParser(description="EdgeFirst Samples - Radar Clusters")
    args.add_argument('-r', '--remote', type=str, default=None,
                      help="Connect to the remote endpoint instead of local.")
    rr.script_add_args(args)
    args = args.parse_args()

    rr.script_setup(args, "radar-clusters")

    # Create the default Zenoh configuration and if the remote argument is
    # provided set the mode to client and add the target to the endpoints.
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    if args.remote is not None:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", '{"endpoints": ["%s"]}' % args.remote)
    session = zenoh.open(config)

    # Create a subscriber for "rt/radar/clusters"
    subscriber = session.declare_subscriber('rt/radar/clusters')

    while True:
        msg = subscriber.recv()
        pcd = PointCloud2.deserialize(msg.payload.to_bytes())
        points = decode_pcd(pcd)
        clusters = [p for p in points if p.id > 0]
        if not clusters:
            rr.log("radar/clusters", rr.Points3D([], colors=[]))  
            continue  
        max_id = max([p.id for p in clusters])
        pos = [[p.x, p.y, p.z] for p in clusters]
        colors = [colormap(turbo_colormap, p.id/max_id) for p in clusters]
        rr.log("radar/clusters", rr.Points3D(pos, colors=colors))
