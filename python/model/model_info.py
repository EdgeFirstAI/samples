# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

import zenoh
from edgefirst.schemas.edgefirst_msgs import ModelInfo
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

# Global variable for message storage
info_msg = None


def info_handler(msg):
    """Simple sync handler that stores message in global."""
    global info_msg
    info_msg = msg


async def info_worker():
    """Async worker that processes messages from global."""
    global info_msg
    while True:
        if info_msg is not None:
            try:
                msg = info_msg
                info = ModelInfo.from_cdr(msg.payload.to_bytes())
                m_type = info.model_type
                m_name = info.model_name
                rr.log("ModelInfo", rr.TextLog("Model Name: %s Model Type: %s" % (m_name, m_type)))
            except Exception as e:
                print(f"Error processing model info message: {e}", file=sys.stderr)
        await asyncio.sleep(0.01)


async def main_async(args):
    # Setup rerun
    args.memory_limit = 10
    rr.script_setup(args, "model-info")

    # Zenoh config
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    remote = format_remote_endpoint(args.remote)
    if remote:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", f'{{"endpoints": ["{remote}"]}}')
    session = zenoh.open(config)

    # Declare subscriber with simple handler
    session.declare_subscriber("rt/model/info", info_handler)
    info_task = asyncio.create_task(info_worker())

    try:
        await asyncio.gather(info_task)
    finally:
        info_task.cancel()
        await asyncio.gather(info_task, return_exceptions=True)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Model Info")
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
