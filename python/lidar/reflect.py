# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

import numpy as np
import rerun as rr
import zenoh
import sys
import asyncio
from argparse import ArgumentParser
from edgefirst.schemas.sensor_msgs import Image

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
reflect_msg = None


def reflect_handler(msg):
    """Simple sync handler that stores message in global."""
    global reflect_msg
    reflect_msg = msg


async def reflect_worker():
    """Async worker that processes messages from global."""
    global reflect_msg
    while True:
        if reflect_msg is not None:
            try:
                msg = reflect_msg
                reflect = Image.from_cdr(msg.payload.to_bytes())

                # Process reflect image
                if reflect.encoding != "mono8":
                    print("Reflect encoding is not mono8")
                else:
                    data = (
                        np.array(reflect.data).reshape((reflect.height, reflect.width)).astype(np.uint8)
                    )
                    rr.log("lidar/depth", rr.Image(data))
            except Exception as e:
                print(f"Error processing reflect message: {e}", file=sys.stderr)
        await asyncio.sleep(0.01)


async def main_async(args):
    # Setup rerun
    args.memory_limit = 10
    rr.script_setup(args, "lidar/reflect")

    # Zenoh config
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    remote = format_remote_endpoint(args.remote)
    if remote:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", f'{{"endpoints": ["{remote}"]}}')
    session = zenoh.open(config)

    # Declare subscriber with simple handler
    session.declare_subscriber("rt/lidar/reflect", reflect_handler)
    reflect_task = asyncio.create_task(reflect_worker())

    try:
        await asyncio.gather(reflect_task)
    finally:
        reflect_task.cancel()
        await asyncio.gather(reflect_task, return_exceptions=True)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Lidar Reflect")
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
