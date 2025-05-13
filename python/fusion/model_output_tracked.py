import zenoh
from edgefirst.schemas.edgefirst_msgs import Mask
import rerun as rr
from argparse import ArgumentParser
import sys
import numpy as np


def main():
    args = ArgumentParser(
        description="EdgeFirst Samples - Fusion Model Output - Tracked")
    args.add_argument('-r', '--remote', type=str, default=None,
                      help="Connect to a Zenoh router rather than local.")
    rr.script_add_args(args)
    args = args.parse_args()

    rr.script_setup(args, "fusion/model_output/tracked")

    # Create the default Zenoh configuration and if the connect argument is
    # provided set the mode to client and add the target to the endpoints.
    config = zenoh.Config()
    if args.remote is not None:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", '{"endpoints": ["%s"]}' % args.remote)
    session = zenoh.open(config)

    # Create a subscriber for "rt/fusion/model_output/tracked"
    subscriber = session.declare_subscriber('rt/fusion/model_output/tracked')

    while True:
        msg = subscriber.recv()
        mask = Mask.deserialize(msg.payload.to_bytes())
        np_arr = np.asarray(mask.mask, dtype=np.uint8)
        np_arr = np.reshape(np_arr, [mask.height, mask.width, -1])
        np_arr = np.argmax(np_arr, axis=2)
        rr.log(
            "/", rr.AnnotationContext([
                (0, "background", (0, 0, 0)),
                (1, "person", (255, 0, 0))]))
        rr.log("mask", rr.SegmentationImage(np_arr))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
