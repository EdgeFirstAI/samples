# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

from argparse import ArgumentParser
import numpy as np
import rerun as rr
import zenoh
import sys
import asyncio
from edgefirst.schemas.edgefirst_msgs import RadarCube

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

cube_msg = None


def cube_handler(msg):
    global cube_msg
    cube_msg = msg


async def cube_worker():
    global cube_msg
    while True:
        if cube_msg is None:
            await asyncio.sleep(0.001)
            continue

        try:
            radar_cube = RadarCube.from_cdr(cube_msg.payload.to_bytes())
        except Exception as e:
            cube_msg = None
            print(f"Error processing radar cube: {e}", file=sys.stderr)
            continue

        cube_msg = None
        data = np.array(radar_cube.cube).reshape(radar_cube.shape)
        # Take the absolute value of the data to improve visualization.
        data = np.abs(data)
        rr.log("radar/cube", rr.Tensor(data, dim_names=["SEQ", "RANGE", "RX", "DOPPLER"]))


async def main_async(args):
    # Setup rerun
    args.memory_limit = 10
    rr.script_setup(args, "radar/cube")

    # Zenoh config
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    if args.remote:
        remote_endpoint = format_remote_endpoint(args.remote)
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", f'{{"endpoints": ["{remote_endpoint}"]}}')
    session = zenoh.open(config)

    session.declare_subscriber("rt/radar/cube", cube_handler)
    cube_task = asyncio.create_task(cube_worker())

    try:
        await asyncio.gather(cube_task)
    finally:
        cube_task.cancel()
        await asyncio.gather(cube_task, return_exceptions=True)



def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Radar Cube")
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
