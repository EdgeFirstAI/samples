from argparse import ArgumentParser
import asyncio
import sys
import av
import io
import zenoh
import time
import threading
import numpy as np
from edgefirst.schemas.edgefirst_msgs import Detect
from edgefirst.schemas.sensor_msgs import PointCloud2
from edgefirst.schemas.geometry_msgs import TransformStamped
from edgefirst.schemas.foxglove_msgs import CompressedVideo as efcv
from edgefirst.schemas import decode_pcd, colormap, turbo_colormap
import threading
import struct
import foxglove
from foxglove.schemas import (CompressedVideo, Timestamp, PointCloud,
                              Pose, Quaternion, Vector3, PackedElementField,
                              PackedElementFieldNumericType, CubePrimitive,
                              SceneEntity, SceneEntityDeletion, 
                              SceneEntityDeletionType, SceneUpdate,
                              FrameTransform, PointsAnnotation, PointsAnnotationType,
                              ImageAnnotations, Point2, Color, TextAnnotation)

class FrameSize:
    def __init__(self):
        self._size = []
        self._event = asyncio.Event()

    def set(self, width, height):
        self._size = [width, height]
        if not self._event.is_set():
            self._event.set()

    async def get(self):
        await self._event.wait()
        return self._size


class MessageDrain:
    def __init__(self, loop):
        self._queue = asyncio.Queue(maxsize=100)
        self._loop = loop

    def callback(self, msg):
        if not self._loop.is_closed():
            if self._queue.full():
                self._queue.get_nowait()
            self._loop.call_soon_threadsafe(self._queue.put_nowait, msg)

    async def read(self):
        return await self._queue.get()

    async def get_latest(self):
        latest = await self._queue.get()
        while not self._queue.empty():
            latest = self._queue.get_nowait()
        return latest
    
def h264_worker(msg, frame_storage, raw_data, container):
    vid = efcv.deserialize(msg.payload.to_bytes())
    if not frame_storage._size:
        raw_data.write(msg.payload.to_bytes())
        raw_data.seek(0)
        for packet in container.demux():
            try:
                if packet.size == 0:
                    continue
                raw_data.seek(0)
                raw_data.truncate(0)
                for frame in packet.decode():
                    frame_array = frame.to_ndarray(format='rgb24')
                    frame_storage.set(frame_array.shape[1], frame_array.shape[0])
            except Exception:
                continue
    foxglove.log(
        "/camera",
        CompressedVideo(
            timestamp=Timestamp(vid.timestamp.sec, vid.timestamp.nanosec),
            frame_id=vid.frame_id,
            data= bytes(vid.data),
            format = vid.format
        )
    )

    
async def h264_handler(drain, frame_storage):
    raw_data = io.BytesIO()
    container = av.open(raw_data, format='h264', mode='r')
    while True:
        msg = await drain.get_latest()
        thread = threading.Thread(target=h264_worker, args=[msg, frame_storage, raw_data, container])
        thread.start()
        
        while thread.is_alive():
            await asyncio.sleep(0.001)
        thread.join()


def boxes2d_worker(msg, boxes_tracked, frame_size):
    detection = Detect.deserialize(msg.payload.to_bytes())
    labels, colors = [], []
    point_annos = []
    label_annos = []
    for box in detection.boxes:
        lx = box.center_x * frame_size[0] - (box.width * frame_size[0] / 2)
        lx = max(0, min(lx, frame_size[0]))
        rx = box.center_x * frame_size[0] + (box.width * frame_size[0] / 2)
        rx = max(0, min(rx, frame_size[0]))
        uy = box.center_y * frame_size[1] - (box.height * frame_size[1] / 2)
        uy = max(0, min(uy, frame_size[1]))
        by = box.center_y * frame_size[1] + (box.height * frame_size[1] / 2)
        by = max(0, min(by, frame_size[1]))

        color = Color(r=0,g=1,b=0,a=1)
        label = TextAnnotation(position=Point2(x=lx, y=by), text=box.label, font_size=32, text_color=Color(r=0,g=0,b=0,a=1),
                               background_color=Color(r=1,g=1,b=1,a=1))
        if box.track.id and box.track.id not in boxes_tracked:
            new_color = np.random.choice(range(256), size=3)
            boxes_tracked[box.track.id] = Color(r=new_color[0] / 255, g=new_color[1] / 255, 
                                                b=new_color[2] / 255, a=1)
        if box.track.id:
            label = TextAnnotation(position=Point2(x=lx, y=by), text=box.label + ": " + box.track.id[:6], font_size=32, 
                                   text_color=Color(r=1,g=1,b=1,a=1), background_color=Color(r=0,g=0,b=0,a=1))
            color = boxes_tracked[box.track.id]

        label_annos.append(label)
        points = [Point2(x=lx, y=uy), Point2(x=lx, y=by), Point2(x=rx, y=by), Point2(x=rx, y=uy)]
        point_annos.append(PointsAnnotation(type=PointsAnnotationType.LineLoop, points=points,
                                            outline_color=color, thickness=5))
    im_anno = ImageAnnotations(points=point_annos, texts=label_annos)
    foxglove.log("/camera/boxes2d", im_anno)


async def boxes2d_handler(drain, frame_storage):
    boxes_tracked = {}
    _ = await frame_storage.get()
    while True:
        msg = await drain.get_latest()
        frame_size = await frame_storage.get()
        thread = threading.Thread(target=boxes2d_worker, args=[msg, boxes_tracked, frame_size])
        thread.start()
        
        while thread.is_alive():
            await asyncio.sleep(0.001)
        thread.join()


def clusters_worker(msg):
    pcd = PointCloud2.deserialize(msg.payload.to_bytes())
    points = decode_pcd(pcd)
    clusters = [p for p in points if p.cluster_id > 0]
    if not clusters:
        return
    
    max_id = max(p.cluster_id for p in clusters)
    point_struct = struct.Struct("<fffffff")
    buffer = bytearray(point_struct.size * len(clusters))

    for i, p in enumerate(clusters):
        color = colormap(turbo_colormap, p.cluster_id / max_id)
        point_struct.pack_into(buffer, i * point_struct.size, p.x, p.y, p.z, 
                               color[0], color[1], 
                               color[2], 1.0)

    pc = PointCloud(
        frame_id=pcd.header.frame_id,
        point_stride=28,  # 4 fields * 4 bytes
        fields=[
            PackedElementField(name="x", offset=0, type=PackedElementFieldNumericType.Float32),
            PackedElementField(name="y", offset=4, type=PackedElementFieldNumericType.Float32),
            PackedElementField(name="z", offset=8, type=PackedElementFieldNumericType.Float32),
            PackedElementField(name="rgba", offset=12, type=PackedElementFieldNumericType.Float32),
        ],
        data=bytes(buffer),
    )
    foxglove.log("/pointcloud/clusters", pc)


async def clusters_handler(drain):
    while True:
        msg = await drain.get_latest()
        thread = threading.Thread(target=clusters_worker, args=[msg])
        thread.start()
        
        while thread.is_alive():
            await asyncio.sleep(0.001)
        thread.join()


def boxes3d_worker(msg):
    detection = Detect.deserialize(msg.payload.to_bytes())
    # The 3D boxes are in an _optical frame of reference, where x is right, y is down, and z (distance) is forward
    # We will convert them to a normal frame of reference, where x is forward, y is left, and z is up
    ts = Timestamp(sec=detection.header.stamp.sec, nsec=detection.header.stamp.nanosec)
    cube_list = []
    for box in detection.boxes:
        cube = CubePrimitive(
            pose=Pose(position=Vector3(x=box.center_x, y=box.center_y, z=box.distance),
                      orientation=Quaternion(x=0, y=0, z=0, w=1)),
            size=Vector3(x=box.width, y=box.height, z=box.width),
            color=(Color(r=0, g=1, b=0, a=0.5))
        )
        cube_list.append(cube)
    entity = SceneEntity(timestamp=ts, frame_id=detection.header.frame_id,
                         id="boxes3d", cubes=cube_list)

    foxglove.log("/pointcloud/boxes3d",
        SceneUpdate(
            deletions=[SceneEntityDeletion(timestamp=ts, type=SceneEntityDeletionType.MatchingId,
                                           id="boxes3d")],
            entities=[entity]
        )
    )


async def boxes3d_handler(drain):
    while True:
        msg = await drain.get_latest()
        thread = threading.Thread(target=boxes3d_worker, args=[msg])
        thread.start()
        
        while thread.is_alive():
            await asyncio.sleep(0.001)
        thread.join()


def static_worker(msg):
    static = TransformStamped.deserialize(msg.payload.to_bytes())
    ts = Timestamp(sec=static.header.stamp.sec, nsec=static.header.stamp.nanosec)
    foxglove.log("/tf_static",
                 FrameTransform(timestamp=ts,
                                parent_frame_id=static.header.frame_id,
                                child_frame_id=static.child_frame_id,
                                translation=Vector3(x=static.transform.translation.x,
                                                    y=static.transform.translation.y,
                                                    z=static.transform.translation.z),
                                rotation=Quaternion(x=static.transform.rotation.x,
                                                    y=static.transform.rotation.y,
                                                    z=static.transform.rotation.z,
                                                    w=static.transform.rotation.w)))



async def static_handler(drain):
    while True:
        msg = await drain.get_latest()
        thread = threading.Thread(target=static_worker, args=[msg])
        thread.start()
        
        while thread.is_alive():
            await asyncio.sleep(0.001)
        thread.join()

    
async def main_async(args):
    _ = foxglove.start_server()

    # Zenoh config
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    if args.remote:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", f'{{"endpoints": ["{args.remote}"]}}')
    session = zenoh.open(config)

    # Create drains
    loop = asyncio.get_running_loop()
    h264_drain = MessageDrain(loop)
    boxes2d_drain = MessageDrain(loop)
    boxes3d_drain = MessageDrain(loop)
    lidar_drain = MessageDrain(loop)
    static_drain = MessageDrain(loop)
    frame_size_storage = FrameSize()

    # Declare subscribers
    session.declare_subscriber('rt/camera/h264', h264_drain.callback)
    session.declare_subscriber('rt/model/boxes2d', boxes2d_drain.callback)
    session.declare_subscriber('rt/lidar/clusters', lidar_drain.callback)
    session.declare_subscriber('rt/fusion/boxes3d', boxes3d_drain.callback)
    session.declare_subscriber('rt/tf_static', static_drain.callback)

    print("All setup")
    # Launch concurrent processing tasks
    await asyncio.gather(h264_handler(h264_drain, frame_size_storage), 
                         boxes2d_handler(boxes2d_drain, frame_size_storage),
                         boxes3d_handler(boxes3d_drain),
                         clusters_handler(lidar_drain),
                         static_handler(static_drain))

    while True:
        asyncio.sleep(0.001)



def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Camera-Lidar")
    parser.add_argument('-r', '--remote', type=str, default=None,
                        help="Connect to the remote endpoint instead of local.")
    args = parser.parse_args()

    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
