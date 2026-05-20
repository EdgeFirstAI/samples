# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

import rerun as rr
import zenoh
import sys
import asyncio
from argparse import ArgumentParser
from edgefirst.schemas.sensor_msgs import NavSatFix

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

gps_msg = None

def gps_handler(msg):
    global gps_msg
    gps_msg = msg


async def gps_worker():
    global gps_msg
    while True:
        if gps_msg is None:
            await asyncio.sleep(0.001)
            continue

        try:
            gps = NavSatFix.from_cdr(gps_msg.payload.to_bytes())
        except Exception as e:
            gps_msg = None
            print(f"Error processing GPS: {e}", file=sys.stderr)
            continue

        gps_msg = None
        rr.log("CurrentLoc", rr.GeoPoints(lat_lon=[gps.latitude, gps.longitude]))


async def main_async(args):
    # Setup rerun
    args.memory_limit = 10
    rr.script_setup(args, "gps")

    # Zenoh config
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    if args.remote:
        remote_endpoint = format_remote_endpoint(args.remote)
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", f'{{"endpoints": ["{remote_endpoint}"]}}')
    session = zenoh.open(config)

    session.declare_subscriber("rt/gps", gps_handler)
    gps_task = asyncio.create_task(gps_worker())

    try:
        await asyncio.gather(gps_task)
    finally:
        gps_task.cancel()
        await asyncio.gather(gps_task, return_exceptions=True)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - GPS")
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
