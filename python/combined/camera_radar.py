from argparse import ArgumentParser
import asyncio
import io
import sys
import av
import zenoh
import rerun as rr
import rerun.blueprint as rrb
from edgefirst.schemas.edgefirst_msgs import Detect
from edgefirst.schemas.sensor_msgs import PointCloud2
from edgefirst.schemas import decode_pcd, colormap, turbo_colormap

raw_data = io.BytesIO()
container = av.open(raw_data, format='h264', mode='r')
frame_size = []
last_h264_msg = None
last_boxes2d_msg = None
last_radar_msg = None

def h264_callback(msg):
    global last_h264_msg
    last_h264_msg = msg

async def h264_processing():
    global last_h264_msg, frame_size
    while True:
        if last_h264_msg is None:
            await asyncio.sleep(0.001)
            continue

        raw_data.write(last_h264_msg.payload.to_bytes())
        raw_data.seek(0)
        for packet in container.demux():
            try:
                if packet.size == 0:
                    continue
                raw_data.seek(0)
                raw_data.truncate(0)
                for frame in packet.decode():
                    frame_array = frame.to_ndarray(format='rgb24')
                    frame_size = [frame_array.shape[1], frame_array.shape[0]]
                    rr.log('camera', rr.Image(frame_array))
            except Exception:
                continue
        last_h264_msg = None
        await asyncio.sleep(0)  # Yield control

def boxes2d_callback(msg):
    global last_boxes2d_msg
    last_boxes2d_msg = msg

async def boxes2d_processing():
    global last_boxes2d_msg, frame_size
    while True:
        if last_boxes2d_msg is None:
            await asyncio.sleep(0.001)
            continue

        if len(frame_size) != 2:
            await asyncio.sleep(0.001)
            continue

        centers, sizes, labels = [], [], []

        detection = Detect.deserialize(last_boxes2d_msg.payload.to_bytes())
        for box in detection.boxes:
            centers.append((int(box.center_x * frame_size[0]), int(box.center_y * frame_size[1])))
            sizes.append((int(box.width * frame_size[0]), int(box.height * frame_size[1])))
            labels.append(box.label)
        rr.log("camera/boxes", rr.Boxes2D(centers=centers, sizes=sizes, labels=labels))
        last_boxes2d_msg = None
        await asyncio.sleep(0)

def radar_clusters_callback(msg):
    global last_radar_msg
    last_radar_msg = msg

async def radar_processing():
    global last_radar_msg
    while True:
        if last_radar_msg is None:
            await asyncio.sleep(0.001)
            continue

        pcd = PointCloud2.deserialize(last_radar_msg.payload.to_bytes())
        points = decode_pcd(pcd)
        clusters = [p for p in points if p.id > 0]
        if not clusters:
            last_radar_msg = None
            await asyncio.sleep(0)
            continue

        max_id = max(p.id for p in clusters)
        pos = [[p.x, p.y, p.z] for p in clusters]
        colors = [colormap(turbo_colormap, p.id / max_id) for p in clusters]
        rr.log("/pointcloud/radar/clusters", rr.Points3D(pos, colors=colors))
        last_radar_msg = None
        await asyncio.sleep(0)

async def main_async(args):
    # Setup rerun
    args.memory_limit = 10
    rr.script_setup(args, "camera_radar")

    blueprint = rrb.Blueprint(
        rrb.Grid(contents=[
            rrb.Spatial2DView(origin="/camera", name="Camera Feed"),
            rrb.Spatial3DView(origin="/pointcloud", name="Pointcloud Clusters")
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
    session.declare_subscriber('rt/radar/clusters', radar_clusters_callback)

    # Launch concurrent processing tasks
    await asyncio.gather(
        h264_processing(),
        boxes2d_processing(),
        radar_processing()
    )

def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Camera Radar")
    parser.add_argument('-r', '--remote', type=str, default=None,
                        help="Connect to the remote endpoint instead of local.")
    rr.script_add_args(parser)
    args = parser.parse_args()

    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == "__main__":
    main()
