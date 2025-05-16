import zenoh
from edgefirst.schemas.sensor_msgs import CompressedImage
import rerun as rr
from argparse import ArgumentParser
import numpy as np
import sys
import cv2

def handler(sample):
    # Deserialize message
    target = CompressedImage.deserialize(sample.payload.to_bytes())
    print(f"Received message: {target}")

def main():
    args = ArgumentParser(description="EdgeFirst Samples - JPEG")
    args.add_argument('-r', '--remote', type=str, default=None,
                      help="Connect to a Zenoh router rather than local.")
    rr.script_add_args(args)
    args = args.parse_args()

    rr.script_setup(args, "jpeg")

    # Create the default Zenoh configuration and if the connect argument is
    # provided set the mode to client and add the target to the endpoints.
    config = zenoh.Config()
    if args.remote is not None:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", '{"endpoints": ["%s"]}' % args.remote)
    session = zenoh.open(config)

    # Create a subscriber for "rt/camera/jpeg"
    subscriber = session.declare_subscriber('rt/camera/jpeg')

    while True:
        msg = subscriber.recv()
        print(msg.timestamp)
        image = CompressedImage.deserialize(msg.payload.to_bytes())
        np_arr = np.frombuffer(bytearray(image.data), np.uint8)
        im = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        im = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
        rr.log('image', rr.Image(im))

if __name__ == "__main__":    
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)