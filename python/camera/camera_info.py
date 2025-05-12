import zenoh
from edgefirst.schemas.sensor_msgs import CameraInfo
import rerun as rr
from argparse import ArgumentParser
import numpy as np
import sys
import cv2


def main():
    args = ArgumentParser(description="EdgeFirst Samples - Camera Info")
    args.add_argument('-r', '--remote', type=str, default=None,
                      help="Connect to a Zenoh router rather than local.")
    rr.script_add_args(args)
    args = args.parse_args()

    rr.script_setup(args, "camera info")

    # Create the default Zenoh configuration and if the connect argument is
    # provided set the mode to client and add the target to the endpoints.
    config = zenoh.Config()
    if args.remote is not None:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", '{"endpoints": ["%s"]}' % args.remote)
    session = zenoh.open(config)

    # Create a subscriber for "rt/camera/info"
    subscriber = session.declare_subscriber('rt/camera/info')

    while True:
        msg = subscriber.recv()
        info = CameraInfo.deserialize(msg.payload.to_bytes())
        width = info.width
        height = info.height
        distortion_model = info.distortion_model
        D = info.d  # Distortion parameters
        K = info.k  # Intrinsic camera matrix
        R = info.r  # Rectification matrix
        P = info.p  # Projection matrix
        rr.log("CameraInfo", rr.TextLog(
            "Camera Width: %d Camera Height: %d" % (width, height)))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
