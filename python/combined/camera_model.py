import zenoh
from edgefirst.schemas.edgefirst_msgs import Detect, Mask
import rerun as rr
from argparse import ArgumentParser
import sys
import av
import io
import time
import zstd
import numpy as np
import cv2

raw_data = io.BytesIO()
container = av.open(raw_data, format='h264', mode='r')
frame_size = []

def h264_callback(msg):
    global frame_size
    raw_data.write(msg.payload.to_bytes())
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

def boxes2d_callback(msg):
    if len(frame_size) != 2:
        return
    centers = []
    sizes = []
    labels = []

    detection = Detect.deserialize(msg.payload.to_bytes())    
    for box in detection.boxes:
        centers.append((int(box.center_x * frame_size[0]), int(box.center_y * frame_size[1])))
        sizes.append((int(box.width * frame_size[0]), int(box.height * frame_size[1])))
        print(centers)
        print(sizes)
        labels.append(box.label)
    rr.log("camera/boxes", rr.Boxes2D(centers=centers, sizes=sizes, labels=labels))

def mask_callback(msg):
    if len(frame_size) != 2:
        return
    mask = Mask.deserialize(msg.payload.to_bytes())
    decoded_array = zstd.decompress(bytes(mask.mask))
    np_arr = np.frombuffer(decoded_array, np.uint8)
    np_arr = np.reshape(np_arr, [mask.height, mask.width, -1])
    np_arr = cv2.resize(np_arr, frame_size)
    np_arr = np.argmax(np_arr, axis=2)
    rr.log("/", rr.AnnotationContext([(0, "background", (0,0,0,0)), (1, "person", (0,255,0))]))
    rr.log("camera/mask", rr.SegmentationImage(np_arr))

def main():
    args = ArgumentParser(description="EdgeFirst Samples - CameraModel")
    args.add_argument('-r', '--remote', type=str, default=None,
                      help="Connect to a Zenoh router rather than local.")
    rr.script_add_args(args)
    args = args.parse_args()

    rr.script_setup(args, "camera_model")

    # Create the default Zenoh configuration and if the connect argument is
    # provided set the mode to client and add the target to the endpoints.
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    if args.remote is not None:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", '{"endpoints": ["%s"]}' % args.remote)
    session = zenoh.open(config)

    # Create the necessary subscribers
    subscriber1 = session.declare_subscriber('rt/camera/h264', h264_callback)
    subscriber2 = session.declare_subscriber('rt/model/boxes2d', boxes2d_callback)
    # Mask callback is currently disabled due to desync caused by cv2 resize
    # subscriber3 = session.declare_subscriber('rt/model/mask_compressed', mask_callback)

    while True:
        time.sleep(0.1)
        

if __name__ == "__main__":    
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)