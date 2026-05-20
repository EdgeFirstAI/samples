# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

import rerun as rr
import zenoh
import sys
import asyncio
from argparse import ArgumentParser
from edgefirst.schemas import decode_pcd
from edgefirst.schemas.sensor_msgs import PointCloud2

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

points_msg = None

def points_handler(msg):
    global points_msg
    points_msg = msg


async def points_worker():
    global points_msg
    while True:
        if points_msg is None:
            await asyncio.sleep(0.001)
            continue

        try:
            pcd = PointCloud2.from_cdr(points_msg.payload.to_bytes())
        except Exception as e:
            points_msg = None
            print(f"Error processing lidar points: {e}", file=sys.stderr)
            continue

        points_msg = None
        points = decode_pcd(pcd)
        pos = [[p.x, p.y, p.z] for p in points]
        rr.log("lidar/points", rr.Points3D(pos))


async def main_async(args):
    # Setup rerun
    args.memory_limit = 10
    rr.script_setup(args, "lidar/points")

    # Zenoh config
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    if args.remote:
        remote_endpoint = format_remote_endpoint(args.remote)
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", f'{{"endpoints": ["{remote_endpoint}"]}}')
    session = zenoh.open(config)

    session.declare_subscriber("rt/lidar/points", points_handler)
    points_task = asyncio.create_task(points_worker())

    try:
        await asyncio.gather(points_task)
    finally:
        points_task.cancel()
        await asyncio.gather(points_task, return_exceptions=True)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Lidar Points")
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
