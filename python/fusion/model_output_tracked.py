# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

import zenoh
from edgefirst.schemas.edgefirst_msgs import Mask
import rerun as rr
from argparse import ArgumentParser
import sys
import numpy as np
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
model_output_msg = None


def model_output_handler(msg):
    """Simple sync handler that stores message in global."""
    global model_output_msg
    model_output_msg = msg


async def model_output_worker():
    """Async worker that processes messages from global."""
    global model_output_msg
    while True:
        if model_output_msg is not None:
            try:
                msg = model_output_msg
                mask = Mask.from_cdr(msg.payload.to_bytes())
                np_arr = np.asarray(mask.mask, dtype=np.uint8)
                np_arr = np.reshape(np_arr, [mask.height, mask.width, -1])
                np_arr = np.argmax(np_arr, axis=2)
                rr.log(
                    "/",
                    rr.AnnotationContext(
                        [(0, "background", (0, 0, 0)), (1, "person", (255, 0, 0))]
                    ),
                )
                rr.log("mask", rr.SegmentationImage(np_arr))
            except Exception as e:
                print(f"Error processing model output tracked message: {e}", file=sys.stderr)
        await asyncio.sleep(0.01)


async def main_async(args):
    # Setup rerun
    args.memory_limit = 10
    rr.script_setup(args, "fusion/model_output/tracked")

    # Zenoh config
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    remote = format_remote_endpoint(args.remote)
    if remote:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", f'{{"endpoints": ["{remote}"]}}')
    session = zenoh.open(config)

    # Declare subscriber with simple handler
    session.declare_subscriber("rt/fusion/model_output/tracked", model_output_handler)
    model_output_task = asyncio.create_task(model_output_worker())

    try:
        await asyncio.gather(model_output_task)
    finally:
        model_output_task.cancel()
        await asyncio.gather(model_output_task, return_exceptions=True)


def main():
    parser = ArgumentParser(
        description="EdgeFirst Samples - Fusion Model Output - Tracked"
    )
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
