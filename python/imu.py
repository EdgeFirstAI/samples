import rerun as rr
import zenoh

from argparse import ArgumentParser
from edgefirst.schemas.sensor_msgs import Imu
from rerun.datatypes import Quaternion


if __name__ == "__main__":
    args = ArgumentParser(description="EdgeFirst Samples - IMU")
    args.add_argument('-r', '--remote', type=str, default=None,
                      help="Connect to the remote endpoint instead of local.")
    rr.script_add_args(args)
    args = args.parse_args()

    rr.script_setup(args, "imu")

    # Create the default Zenoh configuration and if the remote argument is
    # provided set the mode to client and add the target to the endpoints.
    config = zenoh.Config()
    if args.remote is not None:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", '{"endpoints": ["%s"]}' % args.remote)
    session = zenoh.open(config)

    # Create a subscriber for "rt/imu"
    subscriber = session.declare_subscriber('rt/imu')

    while True:
        msg = subscriber.recv()

        # deserialize message
        imu = Imu.deserialize(msg.payload.to_bytes())
        x = imu.orientation.x
        y = imu.orientation.y
        z = imu.orientation.z
        w = imu.orientation.w
        rr.log("box",
               rr.Transform3D(clear=False,
                              quaternion=Quaternion(xyzw=[x, y, z, w])))
