import zenoh
from edgefirst.schemas.edgefirst_msgs import Detect
import rerun as rr
from argparse import ArgumentParser
import sys

def main():
    args = ArgumentParser(description="EdgeFirst Samples - Boxes2D")
    args.add_argument('-r', '--remote', type=str, default=None,
                      help="Connect to a Zenoh router rather than local.")
    rr.script_add_args(args)
    args = args.parse_args()

    rr.script_setup(args, "boxes2d")

    # Create the default Zenoh configuration and if the connect argument is
    # provided set the mode to client and add the target to the endpoints.
    config = zenoh.Config()
    if args.remote is not None:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", '{"endpoints": ["%s"]}' % args.remote)
    session = zenoh.open(config)

    # Create a subscriber for "rt/camera/jpeg"
    subscriber = session.declare_subscriber('rt/model/boxes2d')

    while True:
        msg = subscriber.recv()
        detection = Detect.deserialize(msg.payload.to_bytes())
        centers = []
        sizes = []
        labels = []
        for box in detection.boxes:
            centers.append((box.center_x, box.center_y))
            sizes.append((box.width, box.height))
            labels.append(box.label)
        rr.log("boxes", rr.Boxes2D(centers=centers, sizes=sizes, labels=labels))


if __name__ == "__main__":    
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)