# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

import zenoh
import sys
import asyncio
from argparse import ArgumentParser
from edgefirst.schemas.edgefirst_msgs import RadarInfo
import rerun as rr

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

info_msg = None


def info_handler(msg):
    global info_msg
    info_msg = msg


async def info_worker():
    global info_msg
    while True:
        if info_msg is None:
            await asyncio.sleep(0.001)
            continue

        try:
            radar_info = RadarInfo.from_cdr(info_msg.payload.to_bytes())
        except Exception as e:
            info_msg = None
            print(f"Error processing radar info: {e}", file=sys.stderr)
            continue

        info_msg = None
        radar_log = "Range Mode: %s\n" % str(radar_info.frequency_sweep)
        radar_log += "Center Band: %s\n" % str(radar_info.center_frequency)
        radar_log += "Sensitivity: %s\n" % str(radar_info.detection_sensitivity)
        radar_log += "Range Toggle: %s\n" % str(radar_info.range_toggle)
        rr.log("RadarInfo", rr.TextLog(radar_log))


async def main_async(args):
    # Setup rerun
    args.memory_limit = 10
    rr.script_setup(args, "radar/info")

    # Zenoh config
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    if args.remote:
        remote_endpoint = format_remote_endpoint(args.remote)
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", f'{{"endpoints": ["{remote_endpoint}"]}}')
    session = zenoh.open(config)

    session.declare_subscriber("rt/radar/info", info_handler)
    info_task = asyncio.create_task(info_worker())

    try:
        await asyncio.gather(info_task)
    finally:
        info_task.cancel()
        await asyncio.gather(info_task, return_exceptions=True)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Radar Info")
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
