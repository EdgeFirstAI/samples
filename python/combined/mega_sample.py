from argparse import ArgumentParser
import time
import rerun as rr
import rerun.blueprint as rrb
import io
import av
import zenoh
import ctypes
import os
import sys
from edgefirst.schemas.sensor_msgs import PointCloud2

raw_data = io.BytesIO()
container = av.open(raw_data, format='h264', mode='r')
frame_size = []

# Constants for syscall
SYS_pidfd_open = 434  # From syscall.h
SYS_pidfd_getfd = 438 # From syscall.h
GETFD_FLAGS = 0

# C bindings to syscall (Linux only)
if sys.platform.startswith('linux'):
    libc = ctypes.CDLL("libc.so.6", use_errno=True)

def pidfd_open(pid: int, flags: int = 0) -> int:
    return libc.syscall(SYS_pidfd_open, pid, flags)

def pidfd_getfd(pidfd: int, target_fd: int, flags: int = GETFD_FLAGS) -> int:
    return libc.syscall(SYS_pidfd_getfd, pidfd, target_fd, flags)

def dma_callback(msg):
    global frame_size
    from edgefirst.schemas.edgefirst_msgs import DmaBuffer
    import mmap

    dma_buf = DmaBuffer.deserialize(msg.payload.to_bytes())
    pidfd = pidfd_open(dma_buf.pid)
    if pidfd < 0:
        return

    fd = pidfd_getfd(pidfd, dma_buf.fd, GETFD_FLAGS)
    if fd < 0:
        return

    frame_size = [dma_buf.width, dma_buf.height]
    # Now fd can be used as a file descriptor
    mm = mmap.mmap(fd, dma_buf.length)
    rr.log("/camera", rr.Image(bytes=mm[:], 
                                width=dma_buf.width, 
                                height=dma_buf.height, 
                                pixel_format=rr.PixelFormat.YUY2))
    mm.close()
    os.close(fd)
    os.close(pidfd)

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

def jpeg_callback(msg):
    global frame_size
    import numpy as np
    import cv2
    from edgefirst.schemas.sensor_msgs import CompressedImage

    image = CompressedImage.deserialize(msg.payload.to_bytes())
    np_arr = np.frombuffer(bytearray(image.data), np.uint8)
    im = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    im = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
    frame_size = [im.shape[0], im.shape[1]]
    rr.log('/camera', rr.Image(im))

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
    rr.log("/metrics/detection_inference", rr.Scalars(float(detection.model_time.sec) + float(detection.model_time.nanosec / 1e9)))

def boxes3d_callback(msg):
    from edgefirst.schemas.edgefirst_msgs import Detect
    detection = Detect.deserialize(msg.payload.to_bytes())

    # The 3D boxes are in an _optical frame of reference, where x is right, y is down, and z (distance) is forward
    # We will convert them to a normal frame of reference, where x is forward, y is left, and z is up
    centers = [(x.distance, -x.center_x, -x.center_y)
                for x in detection.boxes]
    sizes = [(x.width, x.width, x.height)
                for x in detection.boxes]

    rr.log("/pointcloud/fusion/boxes", rr.Boxes3D(centers=centers, sizes=sizes))

def mask_callback(msg):
    import numpy as np
    from edgefirst.schemas.edgefirst_msgs import Mask
    if len(frame_size) != 2:
        return
    mask = Mask.deserialize(msg.payload.to_bytes())
    np_arr = np.asarray(mask.mask, dtype=np.uint8)
    np_arr = np.reshape(np_arr, [mask.height, mask.width, -1])
    np_arr = np.argmax(np_arr, axis=2)
    rr.log("/", rr.AnnotationContext([(0, "background", (0,0,0)), (1, "person", (0,255,0))]))
    rr.log("/camera/mask", rr.SegmentationImage(np_arr))

def mask_compressed_callback(msg):
    import zstd
    import cv2
    import numpy as np
    from edgefirst.schemas.edgefirst_msgs import Mask
    if len(frame_size) != 2:
        return
    mask = Mask.deserialize(msg.payload.to_bytes())
    decoded_array = zstd.decompress(bytes(mask.mask))
    np_arr = np.frombuffer(decoded_array, np.uint8)
    np_arr = np.reshape(np_arr, [mask.height, mask.width, -1])
    np_arr = cv2.resize(np_arr, frame_size)
    np_arr = np.argmax(np_arr, axis=2)
    rr.log("/", rr.AnnotationContext([(0, "background", (0,0,0,0)), (1, "person", (0,255,0))]))
    rr.log("/camera/mask", rr.SegmentationImage(np_arr))

def imu_callback(msg):
    from edgefirst.schemas.sensor_msgs import Imu
    from rerun.datatypes import Quaternion
    imu = Imu.deserialize(msg.payload.to_bytes())
    x = imu.orientation.x
    y = imu.orientation.y
    z = imu.orientation.z
    w = imu.orientation.w
    rr.log("imu",
            rr.Transform3D(clear=False,
                            quaternion=Quaternion(xyzw=[x, y, z, w])))
    
def gps_callback(msg):
    from edgefirst.schemas.sensor_msgs import NavSatFix
    gps = NavSatFix.deserialize(msg.payload.to_bytes())
    rr.log("/gps",
            rr.GeoPoints(lat_lon=[gps.latitude, gps.longitude]))
    
def fusion_radar_callback(msg):
    # from edgefirst.schemas.sensor_msgs import PointCloud2
    from edgefirst.schemas import decode_pcd, colormap, turbo_colormap
    pcd = PointCloud2.deserialize(msg.payload.to_bytes())
    points = decode_pcd(pcd)
    max_class = max(max([p.fields["vision_class"] for p in points]), 1)
    pos = [[p.x, p.y, p.z] for p in points]
    colors = [
        colormap(turbo_colormap, p.fields["vision_class"]/max_class) for p in points]
    for i in range(len(colors)):
        for j in range(len(colors[i])):
            colors[i][j] = 1 - colors[i][j]
    rr.log("/pointcloud/fusion/radar", rr.Points3D(positions=pos, colors=colors))

def radar_clusters_callback(msg):
    # from edgefirst.schemas.sensor_msgs import PointCloud2
    from edgefirst.schemas import decode_pcd, colormap, turbo_colormap
    pcd = PointCloud2.deserialize(msg.payload.to_bytes())
    points = decode_pcd(pcd)
    clusters = [p for p in points if p.id > 0]
    max_id = max(max([p.id for p in clusters]), 1)
    pos = [[p.x, p.y, p.z] for p in clusters]
    colors = [colormap(turbo_colormap, p.id/max_id) for p in clusters]
    rr.log("/pointcloud/radar/clusters", rr.Points3D(pos, colors=colors))

def lidar_clusters_callback(msg):
    # from edgefirst.schemas.sensor_msgs import PointCloud2
    from edgefirst.schemas import decode_pcd, colormap, turbo_colormap
    pcd = PointCloud2.deserialize(msg.payload.to_bytes())
    points = decode_pcd(pcd)
    clusters = [p for p in points if p.id > 0]
    max_id = max(max([p.id for p in clusters]), 1)
    pos = [[p.x, p.y, p.z] for p in clusters]
    colors = [colormap(turbo_colormap, p.id/max_id) for p in clusters]
    rr.log("/pointcloud/lidar/clusters", rr.Points3D(pos, colors=colors))

def main():
    args = ArgumentParser(description="EdgeFirst Samples - Mega Sample")
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

    # Create a subscriber for all topics matching the pattern "rt/**"
    subscriber = session.declare_subscriber('rt/**')

    # Keep a list of discovered topics to avoid noise from duplicates
    camera_topics = set()
    model_topics = set()
    radar_topics = set()
    fusion_topics = set()
    lidar_topics = set()
    misc_topics = set()
    start = time.time()

    print("Gathering available topics")
    while True:
        if time.time() - start >= 5:
            break
        msg = subscriber.recv()

        # Ignore message if the topic is known otherwise save the topic
        topic = str(msg.key_expr)
        if 'rt/camera' in topic:
            if topic not in camera_topics:
                camera_topics.add(topic)
        elif 'rt/model' in topic:
            if topic not in model_topics:
                model_topics.add(topic)
        elif 'rt/radar' in topic:
            if topic not in radar_topics:
                radar_topics.add(topic)
        elif 'rt/fusion' in topic:
            if topic not in fusion_topics:
                fusion_topics.add(topic)
        elif 'rt/lidar' in topic:
            if topic not in lidar_topics:
                lidar_topics.add(topic)
        else:
            if topic not in misc_topics:
                misc_topics.add(topic)

    subscriber.undeclare()
    del subscriber

    args.memory_limit=10
    rr.script_setup(args, "mega_sample")
    blueprint = rrb.Blueprint(
        rrb.Grid(contents=[
            rrb.MapView(origin='/gps', name="GPS"),
            rrb.Spatial2DView(origin="/camera", name="Camera Feed"),
            rrb.Spatial3DView(origin="/pointcloud", name="Pointcloud Clusters"),
            rrb.TimeSeriesView(origin="/metrics", name="Model Information")
        ])
    )
    rr.send_blueprint(blueprint)

    cam_subscriber = None
    boxes2d_subscriber = None
    mask_subscriber = None
    imu_subscriber = None
    gps_subscriber = None
    fusion_radar_subscriber = None
    fusion_boxes3d_subscriber = None
    radar_clusters_subscriber = None
    lidar_clusters_subscriber = None

    cam_topic = None
    if args.remote is None and 'rt/camera/dma' in camera_topics:
        cam_topic = 'rt/camera/dma'
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        cam_subscriber = session.declare_subscriber(cam_topic, dma_callback)
    elif 'rt/camera/h264' in camera_topics:
        cam_topic = 'rt/camera/h264'
        cam_subscriber = session.declare_subscriber(cam_topic, h264_callback)
    elif 'rt/camera/jpeg' in camera_topics:
        cam_topic = 'rt/camera/jpeg'
        cam_subscriber = session.declare_subscriber(cam_topic, jpeg_callback)
    else:
        print("No camera topic available")

    if 'rt/model/boxes2d' in model_topics:
        boxes2d_subscriber = session.declare_subscriber('rt/model/boxes2d', boxes2d_callback)

    # if args.remote is None and 'rt/model/mask' in model_topics:
    #     mask_subscriber = session.declare_subscriber('rt/model/mask', mask_callback)
    # elif args.remote is not None and 'rt/model/mask_compressed' in model_topics:
    #     mask_subscriber = session.declare_subscriber('rt/model/mask_compressed', mask_compressed_callback)
    # elif 'rt/model/mask' in model_topics:
    #     mask_subscriber = session.declare_subscriber('rt/model/mask', mask_callback)
    # elif 'rt/model/mask_compressed' in model_topics:
    #     mask_subscriber = session.declare_subscriber('rt/model/mask_compressed', mask_compressed_callback)

    # if 'rt/imu' in misc_topics:
    #     rr.log("/imu", rr.Boxes3D(half_sizes=[[0.5, 0.5, 0.5]], fill_mode="solid"))
    #     rr.log("/imu", rr.Transform3D(axis_length=2))
    #     imu_subscriber = session.declare_subscriber('rt/imu', imu_callback)

    if 'rt/gps' in misc_topics:
        gps_subscriber = session.declare_subscriber('rt/gps', gps_callback)

    # if 'rt/fusion/radar' in fusion_topics:
    #     fusion_radar_subscriber = session.declare_subscriber('rt/fusion/radar', fusion_radar_callback)
    if 'rt/fusion/boxes3d' in fusion_topics:
        fusion_boxes3d_subscriber = session.declare_subscriber('rt/fusion/boxes3d', boxes3d_callback)

    if 'rt/radar/clusters' in radar_topics:
        radar_clusters_subscriber = session.declare_subscriber('rt/radar/clusters', radar_clusters_callback)

    if 'rt/lidar/clusters' in lidar_topics:
        lidar_clusters_subscriber = session.declare_subscriber('rt/lidar/clusters', lidar_clusters_callback)


        

    while True:
        try:
            time.sleep(0.01)
        except KeyboardInterrupt:
            if cam_subscriber:
                cam_subscriber.undeclare()
            if boxes2d_subscriber:
                boxes2d_subscriber.undeclare()
            if mask_subscriber:
                mask_subscriber.undeclare()
            if imu_subscriber:
                imu_subscriber.undeclare()
            if gps_subscriber:
                gps_subscriber.undeclare()
            if fusion_radar_subscriber:
                fusion_radar_subscriber.undeclare()
            if fusion_boxes3d_subscriber:
                fusion_boxes3d_subscriber.undeclare()
            if radar_clusters_subscriber:
                radar_clusters_subscriber.undeclare()
            if lidar_clusters_subscriber:
                lidar_clusters_subscriber.undeclare()
            rr.disconnect()
            break
            

if __name__ == "__main__":    
    main()


    
