# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

import zenoh
from edgefirst.schemas.edgefirst_msgs import DmaBuffer
import rerun as rr
import rerun.blueprint as rrb
from argparse import ArgumentParser
import sys
import mmap
import ctypes
import os
import asyncio
import time
import threading

# Constants for syscall
SYS_pidfd_open = 434  # From syscall.h
SYS_pidfd_getfd = 438  # From syscall.h
GETFD_FLAGS = 0

# C bindings to syscall (Linux only)
if sys.platform.startswith("linux"):
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
else:
    print("DMA only works on EdgeFirst Platforms")
    sys.exit(0)

# Global variable for message storage
dma_msg = None


def pidfd_open(pid: int, flags: int = 0) -> int:
    return libc.syscall(SYS_pidfd_open, pid, flags)


def pidfd_getfd(pidfd: int, target_fd: int, flags: int = GETFD_FLAGS) -> int:
    return libc.syscall(SYS_pidfd_getfd, pidfd, target_fd, flags)


def dma_handler(msg):
    """Simple sync handler that stores message in global."""
    global dma_msg
    dma_msg = msg


async def dma_worker():
    """Async worker that processes messages from global."""
    global dma_msg
    while True:
        if dma_msg is not None:
            try:
                msg = dma_msg
                dma_buf = DmaBuffer.from_cdr(msg.payload.to_bytes())
                pidfd = pidfd_open(dma_buf.pid)
                if pidfd < 0:
                    await asyncio.sleep(0.01)
                    continue

                fd = pidfd_getfd(pidfd, dma_buf.fd, GETFD_FLAGS)
                if fd < 0:
                    await asyncio.sleep(0.01)
                    continue

                # Now fd can be used as a file descriptor
                mm = mmap.mmap(fd, dma_buf.length)
                rr.log(
                    "/camera",
                    rr.Image(
                        bytes=mm[:],
                        width=dma_buf.width,
                        height=dma_buf.height,
                        pixel_format=rr.PixelFormat.YUY2,
                    ),
                )
                mm.close()
                os.close(fd)
                os.close(pidfd)
            except Exception as e:
                print(f"Error processing DMA message: {e}", file=sys.stderr)
        await asyncio.sleep(0.01)


async def main_async(args):
    # Setup rerun
    args.memory_limit = 10
    rr.script_setup(args, "camera-dma")
    blueprint = rrb.Blueprint(
        rrb.Grid(contents=[rrb.Spatial2DView(origin="/camera", name="Camera Feed")])
    )
    rr.send_blueprint(blueprint)

    if args.remote:
        print("DMA example is only functional when run on an EdgeFirst Platform")
        return

    # Zenoh config
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    session = zenoh.open(config)

    # Declare subscriber with simple handler
    session.declare_subscriber("rt/camera/dma", dma_handler)
    dma_task = asyncio.create_task(dma_worker())
    
    # Start worker task
    try:
        await asyncio.gather(dma_task)
    finally:
        dma_task.cancel()
        await asyncio.gather(dma_task, return_exceptions=True)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - DMA")
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
