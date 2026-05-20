# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

import zenoh
from edgefirst.schemas.edgefirst_msgs import Model
from argparse import ArgumentParser
import sys
import rerun as rr
import asyncio
import numpy as np

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

boxes2d_msg = None
boxes_tracked = {}


def boxes2d_handler(msg):
    global boxes2d_msg
    boxes2d_msg = msg


async def boxes2d_worker():
    global boxes2d_msg, boxes_tracked
    while True:
        if boxes2d_msg is None:
            await asyncio.sleep(0.001)
            continue

        try:
            detection = Model.from_cdr(boxes2d_msg.payload.to_bytes())
        except Exception as e:
            boxes2d_msg = None
            print(f"Error processing boxes2d: {e}", file=sys.stderr)
            continue

        boxes2d_msg = None
        centers = []
        sizes = []
        labels = []
        colors = []
        for box in detection.boxes:
            if box.track_id and box.track_id not in boxes_tracked:
                boxes_tracked[box.track_id] = [
                    box.label + ": " + box.track_id[:6],
                    list(np.random.choice(range(256), size=3)),
                ]
            if box.track_id:
                colors.append(boxes_tracked[box.track_id][1])
                labels.append(boxes_tracked[box.track_id][0])
            else:
                colors.append([0, 255, 0])
                labels.append(box.label)
            centers.append((box.center_x, box.center_y))
            sizes.append((box.width, box.height))
        rr.log(
            "boxes", rr.Boxes2D(centers=centers, sizes=sizes, labels=labels, colors=colors)
        )


async def main_async(args):
    # Setup rerun
    args.memory_limit = 10
    rr.script_setup(args, "model-boxes2d")

    # Zenoh config
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    if args.remote:
        remote_endpoint = format_remote_endpoint(args.remote)
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", f'{{"endpoints": ["{remote_endpoint}"]}}')
    session = zenoh.open(config)

    session.declare_subscriber("rt/model/boxes2d", boxes2d_handler)
    boxes2d_task = asyncio.create_task(boxes2d_worker())

    try:
        await asyncio.gather(boxes2d_task)
    finally:
        boxes2d_task.cancel()
        await asyncio.gather(boxes2d_task, return_exceptions=True)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Boxes2D Tracked")
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
