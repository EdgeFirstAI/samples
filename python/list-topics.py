# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

from argparse import ArgumentParser
from time import time
import zenoh

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

if __name__ == "__main__":
    args = ArgumentParser(description="EdgeFirst Samples - List Topics")
    args.add_argument(
        "-r",
        "--remote",
        type=str,
        default=None,
        help="Connect to the remote endpoint instead of local.",
    )
    args.add_argument(
        "-t",
        "--time",
        type=float,
        default=None,
        help="Time in seconds to run command before exiting.",
    )
    args = args.parse_args()

    # Create the default Zenoh configuration and if the remote argument is
    # provided set the mode to client and add the target to the endpoints.
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    if args.remote is not None:
        remote_endpoint = format_remote_endpoint(args.remote)
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", f'{{"endpoints": ["{remote_endpoint}"]}}')
    session = zenoh.open(config)

    # Create a subscriber for all topics matching the pattern "rt/**"
    subscriber = session.declare_subscriber("rt/**")

    # Keep a list of discovered topics to avoid noise from duplicates
    topics = set()
    start = time()

    while True:
        if args.time is not None and time() - start >= args.time:
            break
        msg = subscriber.recv()

        # Ignore message if the topic is known otherwise save the topic
        topic = str(msg.key_expr)
        if topic in topics:
            continue
        topics.add(topic)

        # Capture the message encoding MIME type then split on the first ';'
        # to get the schema.
        schema = str(msg.encoding).split(";", maxsplit=1)[-1]
        print("topic: %s → %s" % (topic, schema))
