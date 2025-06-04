import zenoh
from edgefirst.schemas.edgefirst_msgs import DmaBuffer
import rerun as rr
from argparse import ArgumentParser
import sys
import mmap
import ctypes
import os

# Constants for syscall
SYS_pidfd_open = 434  # From syscall.h
SYS_pidfd_getfd = 438 # From syscall.h
GETFD_FLAGS = 0

# C bindings to syscall (Linux only)
libc = ctypes.CDLL("libc.so.6", use_errno=True)

def pidfd_open(pid: int, flags: int = 0) -> int:
    return libc.syscall(SYS_pidfd_open, pid, flags)

def pidfd_getfd(pidfd: int, target_fd: int, flags: int = GETFD_FLAGS) -> int:
    return libc.syscall(SYS_pidfd_getfd, pidfd, target_fd, flags)

def main():
    args = ArgumentParser(description="EdgeFirst Samples - DMA")
    args.add_argument('-r', '--remote', type=str, default=None,
                      help="Connect to a Zenoh router rather than local.")
    rr.script_add_args(args)
    args = args.parse_args()

    rr.script_setup(args, "dma")

    # Create the default Zenoh configuration and if the connect argument is
    # provided set the mode to client and add the target to the endpoints.
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    if args.remote is not None:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", '{"endpoints": ["%s"]}' % args.remote)
    session = zenoh.open(config)

    # Create a subscriber for "rt/camera/dma"
    subscriber = session.declare_subscriber('rt/camera/dma')

    while True:
        msg = subscriber.recv()
        dma_buf = DmaBuffer.deserialize(msg.payload.to_bytes())
        pidfd = pidfd_open(dma_buf.pid)
        if pidfd < 0:
            continue

        fd = pidfd_getfd(pidfd, dma_buf.fd, GETFD_FLAGS)
        if fd < 0:
            continue

        # Now fd can be used as a file descriptor
        mm = mmap.mmap(fd, dma_buf.length)
        rr.log("image", rr.Image(bytes=mm[:], 
                                 width=dma_buf.width, 
                                 height=dma_buf.height, 
                                 pixel_format=rr.PixelFormat.YUY2))
        mm.close()
        os.close(fd)
        os.close(pidfd)


if __name__ == "__main__":    
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)