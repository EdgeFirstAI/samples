# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

import rerun as rr
import zenoh
from argparse import ArgumentParser
from edgefirst.schemas import turbo_colormap, colormap, decode_pcd
from edgefirst.schemas.sensor_msgs import PointCloud2
import asyncio
import sys

def format_remote_endpoint(remote):
    if not remote:
        return None
    
    # Already in full format (tcp/IP:PORT)
    if remote.startswith("tcp/") and ":" in remote.split("/", 1)[1]:
        return remote
    
    # Just IP address (e.g., "10.10.41.100")
    if "/" not in remote and ":" not in remote:
        return f"tcp/{remote}:7447"
    
    # IP:PORT format (e.g., "10.10.41.100:7447")
    if ":" in remote and not remote.startswith("tcp/"):
        return f"tcp/{remote}"
    
    # tcp/IP format (e.g., "tcp/10.10.41.100")
    if remote.startswith("tcp/") and ":" not in remote.split("/", 1)[1]:
        return f"{remote}:7447"
    
    # Fallback: return as-is
    return remote

clusters_msg = None

def clusters_handler(msg):
    global clusters_msg
    clusters_msg = msg


async def clusters_worker():
    global clusters_msg
    while True:
        if clusters_msg is None:
            await asyncio.sleep(0.001)
            continue

        try:
            pcd = PointCloud2.from_cdr(clusters_msg.payload.to_bytes())
        except Exception as e:
            clusters_msg = None
            print(f"Error processing lidar clusters: {e}", file=sys.stderr)
            continue

        clusters_msg = None
        points = decode_pcd(pcd)
        clusters = [p for p in points if p.cluster_id > 0]
        if not clusters:
            rr.log("lidar/clusters", rr.Points3D([], colors=[]))
            continue
        max_id = max(p.cluster_id for p in clusters)
        pos = [[p.x, p.y, p.z] for p in clusters]
        colors = [colormap(turbo_colormap, p.cluster_id / max_id) for p in clusters]
        rr.log("lidar/clusters", rr.Points3D(pos, colors=colors))


async def main_async(args):
    # Setup rerun
    args.memory_limit = 10
    rr.script_setup(args, "lidar/clusters")

    # Zenoh config
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    if args.remote:
        remote_endpoint = format_remote_endpoint(args.remote)
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", f'{{"endpoints": ["{remote_endpoint}"]}}')
    session = zenoh.open(config)

    session.declare_subscriber("rt/lidar/clusters", clusters_handler)
    clusters_task = asyncio.create_task(clusters_worker())

    try:
        await asyncio.gather(clusters_task)
    finally:
        clusters_task.cancel()
        await asyncio.gather(clusters_task, return_exceptions=True)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Lidar Clusters")
    parser.add_argument(
        "-r",
        "--remote",
        type=str,
        default=None,
        help="Connect to remote endpoint (e.g., '10.10.41.100' or 'tcp/10.10.41.100:7447').",
    )
    rr.script_add_args(parser)
    args = parser.parse_args()

    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
