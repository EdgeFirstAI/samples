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
occupancy_msg = None


def occupancy_handler(msg):
    """Simple sync handler that stores message in global."""
    global occupancy_msg
    occupancy_msg = msg


async def occupancy_worker():
    """Async worker that processes messages from global."""
    global occupancy_msg
    while True:
        if occupancy_msg is not None:
            try:
                msg = occupancy_msg
                pcd = PointCloud2.from_cdr(msg.payload.to_bytes())
                points = decode_pcd(pcd)
                if not points:
                    rr.log("fusion/occupancy", rr.Points3D(positions=[], colors=[]))
                else:
                    max_class = max(max([p.vision_class for p in points]), 1)
                    pos = [[p.x, p.y, p.z] for p in points]
                    colors = [colormap(turbo_colormap, p.vision_class / max_class) for p in points]
                    rr.log("fusion/occupancy", rr.Points3D(positions=pos, colors=colors))
            except Exception as e:
                print(f"Error processing occupancy message: {e}", file=sys.stderr)
        await asyncio.sleep(0.01)


async def main_async(args):
    # Setup rerun
    args.memory_limit = 10
    rr.script_setup(args, "fusion/occupancy")

    # Zenoh config
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    remote = format_remote_endpoint(args.remote)
    if remote:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", f'{{"endpoints": ["{remote}"]}}')
    session = zenoh.open(config)

    # Declare subscriber with simple handler
    session.declare_subscriber("rt/fusion/occupancy", occupancy_handler)
    occupancy_task = asyncio.create_task(occupancy_worker())

    try:
        await asyncio.gather(occupancy_task)
    finally:
        occupancy_task.cancel()
        await asyncio.gather(occupancy_task, return_exceptions=True)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Fusion Occupancy")
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
