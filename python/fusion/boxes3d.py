# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

import zenoh
from edgefirst.schemas.edgefirst_msgs import Detect
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
boxes3d_msg = None


def boxes3d_handler(msg):
    """Simple sync handler that stores message in global."""
    global boxes3d_msg
    boxes3d_msg = msg


async def boxes3d_worker():
    """Async worker that processes messages from global."""
    global boxes3d_msg
    while True:
        if boxes3d_msg is not None:
            try:
                msg = boxes3d_msg
                detection = Detect.from_cdr(msg.payload.to_bytes())
                # The 3D boxes are in an _optical frame of reference, where x is right, y is down, and z (distance) is forward
                # We will convert them to a normal frame of reference, where x is forward, y is left, and z is up
                centers = [(x.distance, -x.center_x, -x.center_y) for x in detection.boxes]
                sizes = [(x.width, x.width, x.height) for x in detection.boxes]
                rr.log("/pointcloud/fusion/boxes", rr.Boxes3D(centers=centers, sizes=sizes))
            except Exception as e:
                print(f"Error processing boxes3d message: {e}", file=sys.stderr)
        await asyncio.sleep(0.01)


async def main_async(args):
    # Setup rerun
    args.memory_limit = 10
    rr.script_setup(args, "fusion-boxes3d")

    # Zenoh config
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    remote = format_remote_endpoint(args.remote)
    if remote:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", f'{{"endpoints": ["{remote}"]}}')
    session = zenoh.open(config)

    # Declare subscriber with simple handler
    session.declare_subscriber("rt/fusion/boxes3d", boxes3d_handler)
    boxes3d_task = asyncio.create_task(boxes3d_worker())
    
    # Start worker task
    try:
        await asyncio.gather(boxes3d_task)
    finally:
        boxes3d_task.cancel()
        await asyncio.gather(boxes3d_task, return_exceptions=True)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Boxes3D")
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
