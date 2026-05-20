# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

from argparse import ArgumentParser
from edgefirst.schemas.sensor_msgs import Image
import numpy as np
import rerun as rr
import struct
import zenoh
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

# Global variable for message storage
depth_msg = None


def depth_handler(msg):
    """Simple sync handler that stores message in global."""
    global depth_msg
    depth_msg = msg


async def depth_worker():
    """Async worker that processes messages from global."""
    global depth_msg
    while True:
        if depth_msg is not None:
            try:
                msg = depth_msg
                depth = Image.from_cdr(msg.payload.to_bytes())

                # Process depth image
                if depth.encoding != "mono16":
                    print("Depth encoding is not mono16")
                else:
                    endian_format = ">" if depth.is_bigendian else "<"
                    depth_vals = list(
                        struct.unpack(f"{endian_format}{depth.width*depth.height}H", bytes(depth.data))
                    )
                    data = (np.array(depth_vals).reshape((depth.height, depth.width)) / 255).astype(
                        np.uint8
                    )
                    rr.log("lidar/depth", rr.Image(data))
            except Exception as e:
                print(f"Error processing depth message: {e}", file=sys.stderr)
        await asyncio.sleep(0.01)


async def main_async(args):
    # Setup rerun
    args.memory_limit = 10
    rr.script_setup(args, "lidar/depth")

    # Zenoh config
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    remote = format_remote_endpoint(args.remote)
    if remote:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", f'{{"endpoints": ["{remote}"]}}')
    session = zenoh.open(config)

    # Declare subscriber with simple handler
    session.declare_subscriber("rt/lidar/depth", depth_handler)
    depth_task = asyncio.create_task(depth_worker())

    try:
        await asyncio.gather(depth_task)
    finally:
        depth_task.cancel()
        await asyncio.gather(depth_task, return_exceptions=True)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Lidar Depth")
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
