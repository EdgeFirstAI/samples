from argparse import ArgumentParser
import time
import rerun as rr
import rerun.blueprint as rrb
import io
import av
import zenoh

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
                rr.log('/camera', rr.Image(frame_array))
        except Exception:  # Handle exceptions
            continue  # Continue processing next packets

def boxes2d_callback(msg):
    from edgefirst.schemas.edgefirst_msgs import Detect
    if len(frame_size) != 2:
        return
    centers = []
    sizes = []
    labels = []

    detection = Detect.deserialize(msg.payload.to_bytes())    
    for box in detection.boxes:
        centers.append((int(box.center_x * frame_size[0]), int(box.center_y * frame_size[1])))
        sizes.append((int(box.width * frame_size[0]), int(box.height * frame_size[1])))
        labels.append(box.label)
    rr.log("/camera/boxes", rr.Boxes2D(centers=centers, sizes=sizes, labels=labels))

def lidar_clusters_callback(msg):
    from edgefirst.schemas.sensor_msgs import PointCloud2
    from edgefirst.schemas import decode_pcd, colormap, turbo_colormap
    pcd = PointCloud2.deserialize(msg.payload.to_bytes())
    points = decode_pcd(pcd)
    clusters = [p for p in points if p.id > 0]
    max_id = max(max([p.id for p in clusters]), 1)
    pos = [[p.x, p.y, p.z] for p in clusters]
    colors = [colormap(turbo_colormap, p.id/max_id) for p in clusters]
    rr.log("/pointcloud/lidar/clusters", rr.Points3D(pos, colors=colors))

def main():
    args = ArgumentParser(description="EdgeFirst Samples - Camera Lidar")
    args.add_argument('-r', '--remote', type=str, default=None,
                      help="Connect to the remote endpoint instead of local.")
    rr.script_add_args(args)
    args = args.parse_args()

    # Create the default Zenoh configuration and if the remote argument is
    # provided set the mode to client and add the target to the endpoints.
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    if args.remote is not None:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", '{"endpoints": ["%s"]}' % args.remote)
    session = zenoh.open(config)

    args.memory_limit=10
    rr.script_setup(args, "mega_sample")
    blueprint = rrb.Blueprint(
        rrb.Grid(contents=[
            rrb.Spatial2DView(origin="/camera", name="Camera Feed"),
            rrb.Spatial3DView(origin="/pointcloud", name="Pointcloud Clusters")
        ])
    )
    rr.send_blueprint(blueprint)

    cam_subscriber = session.declare_subscriber('rt/camera/h264', h264_callback)
    boxes2d_subscriber = session.declare_subscriber('rt/model/boxes2d', boxes2d_callback)
    lidar_clusters_subscriber = session.declare_subscriber('rt/lidar/clusters', lidar_clusters_callback)

    while True:
        try:
            time.sleep(0.1)
        except KeyboardInterrupt:
            if cam_subscriber:
                cam_subscriber.undeclare()
            if boxes2d_subscriber:
                boxes2d_subscriber.undeclare()
            if lidar_clusters_subscriber:
                lidar_clusters_subscriber.undeclare()
            rr.disconnect()
            break
            

if __name__ == "__main__":    
    main()


    
