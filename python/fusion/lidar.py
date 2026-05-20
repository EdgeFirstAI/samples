# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

import zenoh
from edgefirst.schemas.sensor_msgs import PointCloud2
from edgefirst.schemas import decode_pcd, colormap, turbo_colormap
from argparse import ArgumentParser
import sys
import rerun as rr
import asyncio

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

# Global variable for message storage
lidar_msg = None


def lidar_handler(msg):
    """Simple sync handler that stores message in global."""
    global lidar_msg
    lidar_msg = msg


async def lidar_worker():
    """Async worker that processes messages from global."""
    global lidar_msg
    while True:
        if lidar_msg is not None:
            try:
                msg = lidar_msg
                pcd = PointCloud2.from_cdr(msg.payload.to_bytes())
                points = decode_pcd(pcd)
                clusters = [p for p in points if p.cluster_id > 0]
                if not clusters:
                    rr.log("fusion/lidar", rr.Points3D([], colors=[]))
                else:
                    max_id = max(p.cluster_id for p in clusters)
                    pos = [[p.x, p.y, p.z] for p in clusters]
                    colors = [colormap(turbo_colormap, p.cluster_id / max_id) for p in clusters]
                    rr.log("fusion/lidar", rr.Points3D(pos, colors=colors))
            except Exception as e:
                print(f"Error processing fusion lidar message: {e}", file=sys.stderr)
        await asyncio.sleep(0.01)


async def main_async(args):
    # Setup rerun
    args.memory_limit = 10
    rr.script_setup(args, "fusion-lidar")

    # Zenoh config
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    remote = format_remote_endpoint(args.remote)
    if remote:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", f'{{"endpoints": ["{remote}"]}}')
    session = zenoh.open(config)

    # Declare subscriber with simple handler
    session.declare_subscriber("rt/fusion/lidar", lidar_handler)
    lidar_task = asyncio.create_task(lidar_worker())

    try:
        await asyncio.gather(lidar_task)
    finally:
        lidar_task.cancel()
        await asyncio.gather(lidar_task, return_exceptions=True)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Fusion - Lidar")
    parser.add_argument(
        "-r",
        "--remote",
        type=str,
        default=None,
        help="Remote endpoint (IP:PORT or just IP, defaults to port 7447)",
    )
    rr.script_add_args(parser)
    args = parser.parse_args()

    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
