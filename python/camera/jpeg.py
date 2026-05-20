# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

import zenoh
from edgefirst.schemas.sensor_msgs import CompressedImage
import rerun as rr
from argparse import ArgumentParser
import numpy as np
import sys
import cv2
import asyncio
import rerun.blueprint as rrb

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
jpeg_msg = None


def jpeg_handler(msg):
    """Simple sync handler that stores message in global."""
    global jpeg_msg
    jpeg_msg = msg


async def jpeg_worker():
    """Async worker that processes messages from global."""
    global jpeg_msg
    while True:
        if jpeg_msg is not None:
            try:
                msg = jpeg_msg
                image = CompressedImage.from_cdr(msg.payload.to_bytes())
                np_arr = np.frombuffer(bytearray(image.data), np.uint8)
                im = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                im = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
                rr.log("/camera", rr.Image(im))
            except Exception as e:
                print(f"Error processing JPEG message: {e}", file=sys.stderr)
        await asyncio.sleep(0.01)


async def main_async(args):
    # Setup rerun
    args.memory_limit = 10
    rr.script_setup(args, "camera-jpeg")
    blueprint = rrb.Blueprint(
        rrb.Grid(contents=[rrb.Spatial2DView(origin="/camera", name="Camera Feed")])
    )
    rr.send_blueprint(blueprint)

    # Zenoh config
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    remote = format_remote_endpoint(args.remote)
    if remote:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", f'{{"endpoints": ["{remote}"]}}')
    session = zenoh.open(config)

    # Declare subscriber with simple handler
    session.declare_subscriber("rt/camera/jpeg", jpeg_handler)
    jpeg_task = asyncio.create_task(jpeg_worker())
    
    # Start worker task
    try:
        await asyncio.gather(jpeg_task)
    finally:
        jpeg_task.cancel()
        await asyncio.gather(jpeg_task, return_exceptions=True)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - JPEG")
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
