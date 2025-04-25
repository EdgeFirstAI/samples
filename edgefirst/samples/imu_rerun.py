import zenoh
from time import time
from argparse import ArgumentParser
from edgefirst.schemas.sensor_msgs import Imu
import rerun as rr
from rerun.datatypes import Quaternion

if __name__ == "__main__":
    args = ArgumentParser(description="EdgeFirst Samples - IMU")
    args.add_argument('-c', '--connect', type=str, default=None,
                      help="Connect to a Zenoh router rather than peer mode.")
    args.add_argument('-t', '--time', type=float, default=None,
                      help="Time in seconds to run command before exiting.")
    args = args.parse_args()

    rr.init("IMU Example", spawn=True)
    box = rr.Boxes3D(half_sizes=[0.5, 0.5, 0.5], fill_mode=rr.components.FillMode.Solid)
    rr.log("box", box, rr.Transform3D(clear=False, axis_length=2),)

    # Create the default Zenoh configuration and if the connect argument is
    # provided set the mode to client and add the target to the endpoints.
    config = zenoh.Config()
    if args.connect is not None:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", '{"endpoints": ["%s"]}' % args.connect)
    session = zenoh.open(config)

    # Create a subscriber for "rt/imu"
    subscriber = session.declare_subscriber('rt/imu')

    # Keep a list of discovered topics to avoid noise from duplicates
    start = time()

    while True:
        if args.time is not None and time() - start >= args.time:
            break
        msg = subscriber.recv()

        # deserialize message
        imu = Imu.deserialize(msg.payload.to_bytes())
        x = imu.orientation.x
        y = imu.orientation.y
        z = imu.orientation.z
        w = imu.orientation.w
        # print("X: %.4f Y: %.4f Z: %.4f W: %.4f" % (x, y, z, w))
        rr.log("box", rr.Transform3D(clear=False, quaternion=Quaternion(xyzw=[x,y,z,w])))


        