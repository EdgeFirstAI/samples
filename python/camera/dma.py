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


def pidfd_open(pid: int, flags: int = 0) -> int:
    return libc.syscall(SYS_pidfd_open, pid, flags)


def pidfd_getfd(pidfd: int, target_fd: int, flags: int = GETFD_FLAGS) -> int:
    return libc.syscall(SYS_pidfd_getfd, pidfd, target_fd, flags)


class MessageDrain:
    def __init__(self, loop):
        self._queue = asyncio.Queue(maxsize=100)
        self._loop = loop

    def callback(self, msg):
        if not self._loop.is_closed():
            if self._queue.full():
                self._queue.get_nowait()
            self._loop.call_soon_threadsafe(self._queue.put_nowait, msg)

    async def read(self):
        return await self._queue.get()

    async def get_latest(self):
        latest = await self._queue.get()
        while not self._queue.empty():
            latest = self._queue.get_nowait()
        return latest


def dma_worker(msg):
    dma_buf = DmaBuffer.deserialize(msg.payload.to_bytes())
    pidfd = pidfd_open(dma_buf.pid)
    if pidfd < 0:
        return

    fd = pidfd_getfd(pidfd, dma_buf.fd, GETFD_FLAGS)
    if fd < 0:
        return

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


async def dma_handler(drain):
    while True:
        msg = await drain.get_latest()
        thread = threading.Thread(target=dma_worker, args=[msg])
        thread.start()

        while thread.is_alive():
            await asyncio.sleep(0.001)
        thread.join()


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
    if args.remote:
        # Ensure remote endpoint has tcp/ prefix
        remote = args.remote if args.remote.startswith("tcp/") else f"tcp/{args.remote}"
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", f'{{"endpoints": ["{remote}"]}}')
    session = zenoh.open(config)

    # Create drains
    loop = asyncio.get_running_loop()
    drain = MessageDrain(loop)

    session.declare_subscriber("rt/camera/dma", drain.callback)
    await asyncio.gather((dma_handler(drain)))

    while True:
        asyncio.sleep(0.001)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - DMA")
    parser.add_argument(
        "-r",
        "--remote",
        type=str,
        default=None,
        help="Connect to the remote endpoint instead of local.",
    )
    rr.script_add_args(parser)
    args = parser.parse_args()

    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
