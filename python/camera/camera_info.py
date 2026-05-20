# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

import zenoh
from edgefirst.schemas.sensor_msgs import CameraInfo
import rerun as rr
from argparse import ArgumentParser
import sys
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

cam_info_msg = None

def cam_info_handler(msg):
    global cam_info_msg
    cam_info_msg = msg


async def cam_info_worker():
    global cam_info_msg
    while True:
        if cam_info_msg is None:
            await asyncio.sleep(0.001)
            continue

        try:
            info = CameraInfo.from_cdr(cam_info_msg.payload.to_bytes())
        except Exception as e:
            cam_info_msg = None
            print(f"Error processing camera info: {e}", file=sys.stderr)
            continue

        cam_info_msg = None
        width = info.width
        height = info.height
        rr.log(
            "CameraInfo", rr.TextLog("Camera Width: %d Camera Height: %d" % (width, height))
        )

async def main_async(args):
    # Setup rerun
    args.memory_limit = 10
    rr.script_setup(args, "camera-info")

    # Zenoh config
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    if args.remote:
        remote_endpoint = format_remote_endpoint(args.remote)
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", f'{{"endpoints": ["{remote_endpoint}"]}}')
    session = zenoh.open(config)

    tasks = []

    session.declare_subscriber("rt/camera/info", cam_info_handler)
    cam_info_task = asyncio.create_task(cam_info_worker())

    try:
        await asyncio.gather(cam_info_task)
    finally:
        cam_info_task.cancel()
        await asyncio.gather(cam_info_task, return_exceptions=True)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Camera Info")
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
