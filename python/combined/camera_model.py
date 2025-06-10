import zenoh
from edgefirst.schemas.edgefirst_msgs import Detect, Mask
import rerun as rr
import rerun.blueprint as rrb
from argparse import ArgumentParser
import sys
import av
import asyncio
import io
import time
import zstd
import numpy as np
import cv2

raw_data = io.BytesIO()
container = av.open(raw_data, format='h264', mode='r')
frame_size = []
last_h264_msg = None
last_boxes2d_msg = None
last_mask_msg = None

def h264_callback(msg):
    global last_h264_msg
    last_h264_msg = msg

async def h264_processing():
    global last_h264_msg
    global frame_size
    while True:
        if last_h264_msg is None:
            time.sleep(0.001)
            continue

        raw_data.write(last_h264_msg.payload.to_bytes())
        raw_data.seek(0)
        for packet in container.demux():
            try:
                if packet.size == 0:  # Skip empty packets
                    continue
                raw_data.seek(0)
                raw_data.truncate(0)
                for frame in packet.decode():  # Decode video frames
                    frame_array = frame.to_ndarray(format='rgb24')  # Convert frame to numpy array
                    frame_size = [frame_array.shape[1], frame_array.shape[0]]
                    rr.log('camera', rr.Image(frame_array))
            except Exception:  # Handle exceptions
                continue  # Continue processing next packets
        last_h264_msg = None

def boxes2d_callback(msg):
    global last_boxes2d_msg
    last_boxes2d_msg = msg

async def boxes2d_processing():
    global last_boxes2d_msg
    while True:
        if last_boxes2d_msg is None:
            time.sleep(0.001)
            continue

        if len(frame_size) != 2:
            return
        centers = []
        sizes = []
        labels = []

        detection = Detect.deserialize(last_boxes2d_msg.payload.to_bytes())    
        for box in detection.boxes:
            centers.append((int(box.center_x * frame_size[0]), int(box.center_y * frame_size[1])))
            sizes.append((int(box.width * frame_size[0]), int(box.height * frame_size[1])))
            labels.append(box.label)
        rr.log("camera/boxes", rr.Boxes2D(centers=centers, sizes=sizes, labels=labels))
        last_boxes2d_msg = None

def mask_callback(msg):
    global last_mask_msg
    last_mask_msg = msg

async def mask_processing():
    global last_mask_msg
    while True:
        if last_mask_msg is None:
            time.sleep(0.001)
            continue

        if len(frame_size) != 2:
            return
        mask = Mask.deserialize(last_mask_msg.payload.to_bytes())
        decoded_array = zstd.decompress(bytes(mask.mask))
        np_arr = np.frombuffer(decoded_array, np.uint8)
        np_arr = np.reshape(np_arr, [mask.height, mask.width, -1])
        np_arr = cv2.resize(np_arr, frame_size)
        np_arr = np.argmax(np_arr, axis=2)
        rr.log("/", rr.AnnotationContext([(0, "background", (0,0,0,0)), (1, "person", (0,255,0))]))
        rr.log("camera/mask", rr.SegmentationImage(np_arr))
        last_mask_msg = None

async def main_async(args):
    # Setup rerun
    args.memory_limit = 10
    rr.script_setup(args, "camera_model")

    blueprint = rrb.Blueprint(
        rrb.Grid(contents=[
            rrb.Spatial2DView(origin="/camera", name="Camera Feed"),
        ])
    )
    rr.send_blueprint(blueprint)

    # Zenoh config
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    if args.remote:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", f'{{"endpoints": ["{args.remote}"]}}')
    session = zenoh.open(config)

    # Declare subscribers
    session.declare_subscriber('rt/camera/h264', h264_callback)
    session.declare_subscriber('rt/model/boxes2d', boxes2d_callback)
    session.declare_subscriber('rt/model/mask_compressed', mask_callback)

    # Launch concurrent processing tasks
    await asyncio.gather(
        h264_processing(),
        boxes2d_processing(),
        mask_processing()
    )

def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Camera Model")
    parser.add_argument('-r', '--remote', type=str, default=None,
                        help="Connect to the remote endpoint instead of local.")
    rr.script_add_args(parser)
    args = parser.parse_args()

    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        sys.exit(0)
        

if __name__ == "__main__":    
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)