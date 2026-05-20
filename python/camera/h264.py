# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

from argparse import ArgumentParser
import asyncio
import sys
import zenoh
import rerun as rr
import rerun.blueprint as rrb
from edgefirst.schemas.foxglove_msgs import CompressedVideo

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
h264_msg = None
video_data_buffer = bytearray()  # Accumulate video data
stream_initialized = False


def is_h264_keyframe(data) -> bool:
    """
    Check if H.264 data contains a keyframe (IDR frame).
    
    Searches for NAL unit type 5 (IDR) or type 7/8 (SPS/PPS) which indicate keyframes.
    H.264 NAL units start with 0x00000001 or 0x000001, followed by a byte where
    the lower 5 bits indicate the NAL unit type.
    
    Args:
        data: Buffer-like object (bytes, memoryview, BorrowedBuf)
    
    Returns:
        True if keyframe detected, False otherwise
    """
    i = 0
    while i < len(data) - 4:
        # Look for start codes: 0x00000001 or 0x000001
        if data[i:i+3] == b'\x00\x00\x01':
            nal_type = data[i+3] & 0x1F  # Lower 5 bits = NAL unit type
            if nal_type in (5, 7, 8):  # IDR (5), SPS (7), PPS (8)
                return True
            i += 3
        elif data[i:i+4] == b'\x00\x00\x00\x01':
            nal_type = data[i+4] & 0x1F
            if nal_type in (5, 7, 8):
                return True
            i += 4
        else:
            i += 1
    return False


def h264_handler(msg):
    """Simple sync handler that stores message in global."""
    global h264_msg
    h264_msg = msg
    
                


async def h264_worker():
    """Async worker that logs H.264 video using VideoStream pattern."""
    global h264_msg
    global video_data_buffer
    global stream_initialized
    
    frame_count = 0
    
    while True:
        if h264_msg is not None:
            try:
                video_msg = CompressedVideo.from_cdr(h264_msg.payload.to_bytes())
                h264_msg = None
                
                # Get zero-copy view of video data
                data_view = video_msg.data.view()
                
                # Accumulate video data (extend accepts memoryview)
                video_data_buffer.extend(data_view)
                
                # Convert ROS2 timestamp to nanoseconds for Rerun
                timestamp_ns = video_msg.timestamp.sec * 1_000_000_000 + video_msg.timestamp.nanosec
                
                # Check if this is a keyframe (works with memoryview)
                is_key = is_h264_keyframe(data_view)
                
                # Initialize stream with first keyframe
                if not stream_initialized and is_key:
                    rr.log(
                        "/camera",
                        rr.AssetVideo(contents=bytes(video_data_buffer), media_type=rr.MediaType.MP4),
                        static=True
                    )
                    stream_initialized = True
                    frame_count = 0
                
                # Log video frame reference
                if stream_initialized:
                    # rr.set_time_nanos("camera_time", timestamp_ns)
                    rr.log(
                        "/camera",
                        rr.VideoFrameReference(
                            timestamp=rr.components.VideoTimestamp.nanoseconds(timestamp_ns),
                            video_reference=frame_count
                        )
                    )
                    frame_count += 1
                    
            except Exception as e:
                print(f"Error processing H.264 message: {e}", file=sys.stderr)
        
        await asyncio.sleep(0.01)


async def main_async(args):
    # Setup rerun
    args.memory_limit = 10
    rr.script_setup(args, "camera-h264")
    blueprint = rrb.Blueprint(
        rrb.Grid(contents=[rrb.Spatial2DView(origin="/camera", name="Camera Feed")])
    )
    rr.send_blueprint(blueprint)

    # Zenoh config
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    if args.remote:
        remote_endpoint = format_remote_endpoint(args.remote)
        print(remote_endpoint)
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", f'{{"endpoints": ["{remote_endpoint}"]}}')
    session = zenoh.open(config)
    
    tasks = []

    session.declare_subscriber("rt/camera/h264", h264_handler)
    h264_task = asyncio.create_task(h264_worker())
    
    # Start worker task
    try:
        await asyncio.gather(h264_task)
    finally:
        h264_task.cancel()
        await asyncio.gather(h264_task, return_exceptions=True)

    while True:
        await asyncio.sleep(0.001)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - H264")
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
