# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

import rerun as rr
import zenoh
import sys
import asyncio
from argparse import ArgumentParser
from edgefirst.schemas.sensor_msgs import Imu
from rerun.datatypes import Quaternion

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

imu_msg = None

def imu_handler(msg):
    global imu_msg
    imu_msg = msg


async def imu_worker():
    global imu_msg
    while True:
        if imu_msg is None:
            await asyncio.sleep(0.001)
            continue

        try:
            imu = Imu.from_cdr(imu_msg.payload.to_bytes())
        except Exception as e:
            imu_msg = None
            print(f"Error processing IMU: {e}", file=sys.stderr)
            continue

        imu_msg = None
        x = imu.orientation.x
        y = imu.orientation.y
        z = imu.orientation.z
        w = imu.orientation.w
        rr.log(
            "/imu", rr.Transform3D(clear=False, quaternion=Quaternion(xyzw=[x, y, z, w]))
        )


async def main_async(args):
    # Setup rerun
    args.memory_limit = 10
    rr.script_setup(args, "imu")

    # Zenoh config
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    if args.remote:
        remote_endpoint = format_remote_endpoint(args.remote)
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", f'{{"endpoints": ["{remote_endpoint}"]}}')
    session = zenoh.open(config)

    rr.log("/imu", rr.Boxes3D(half_sizes=[[0.5, 0.5, 0.5]], fill_mode="solid"))
    rr.log("/imu", rr.Transform3D(axis_length=2))

    session.declare_subscriber("rt/imu", imu_handler)
    imu_task = asyncio.create_task(imu_worker())

    try:
        await asyncio.gather(imu_task)
    finally:
        imu_task.cancel()
        await asyncio.gather(imu_task, return_exceptions=True)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - IMU")
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
