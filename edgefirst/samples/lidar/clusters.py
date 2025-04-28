import zenoh
from edgefirst.schemas.sensor_msgs import PointCloud2, PointField, PointFieldDatatype
import struct
from argparse import ArgumentParser
from time import time
import rerun


class LidarPoint:
    def __init__(self):
        self.x = 0
        self.y = 0
        self.z = 0
        self.fields = dict()


SIZE_OF_DATATYPE = [
    0,
    1,  # pub const INT8: u8= 1
    1,  # pub const UINT8: u8= 2
    2,  # pub const INT16: u8= 3
    2,  # pub const UINT16: u8= 4
    4,  # pub const INT32: u8= 5
    4,  # pub const UINT32: u8= 6
    4,  # pub const FLOAT32: u8= 7
    8,  # pub const FLOAT64: u8 = 8
]

STRUCT_LETTER_OF_DATATYPE = [
    "",
    "b",  # pub const INT8: u8= 1
    "B",  # pub const UINT8: u8= 2
    "h",  # pub const INT16: u8= 3
    "H",  # pub const UINT16: u8= 4
    "i",  # pub const INT32: u8= 5
    "I",  # pub const UINT32: u8= 6
    "f",  # pub const FLOAT32: u8= 7
    "d",  # pub const FLOAT64: u8 = 8
]


def decode_pcd(pcd: PointCloud2) -> list[LidarPoint]:
    points = []
    endian_format = ">" if pcd.is_bigendian else "<"
    for i in range(pcd.height):
        for j in range(pcd.width):
            point = LidarPoint()
            point_start = (i * pcd.width + j) * pcd.point_step
            # Loop through the provided Fields for each Point (x, y, z, speed,
            # power, rcs)
            for f in pcd.fields:
                val = 0
                # Decode the data according to the datatype and endian format stated
                # in the message, location in the array block determined
                # through the offset
                arr = bytearray(
                    pcd.data[(point_start + f.offset):(point_start + f.offset + SIZE_OF_DATATYPE[f.datatype])])
                val = struct.unpack(
                    f'{endian_format}{STRUCT_LETTER_OF_DATATYPE[f.datatype]}', arr)[0]
                if f.name == "x":
                    point.x = val
                if f.name == "y":
                    point.y = val
                if f.name == "z":
                    point.z = val
                if f.name == "cluster_id":
                    point.id = int(val)
            points.append(point)
    return points


if __name__ == "__main__":
    args = ArgumentParser(description="EdgeFirst Samples - Lidar Clusters")
    args.add_argument('-c', '--connect', type=str, default=None,
                      help="Connect to a Zenoh router rather than peer mode.")
    args.add_argument('-t', '--time', type=float, default=None,
                      help="Time in seconds to run command before exiting.")
    args = args.parse_args()

    # Create the default Zenoh configuration and if the connect argument is
    # provided set the mode to client and add the target to the endpoints.
    config = zenoh.Config()
    if args.connect is not None:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", '{"endpoints": ["%s"]}' % args.connect)
    session = zenoh.open(config)

    # Create a subscriber for "rt/lidar/clusters"
    subscriber = session.declare_subscriber('rt/lidar/clusters')

    start = time()

    while True:
        if args.time is not None and time() - start >= args.time:
            break
        msg = subscriber.recv()

        # deserialize message
        pcd = PointCloud2.deserialize(msg.payload.to_bytes())
        points = decode_pcd(pcd)
        clustered_points = [p for p in points if p.id > 0]
        print(
            f"Recieved {len(points)} lidar points. {len(clustered_points)} are clustered")
