from argparse import ArgumentParser
import asyncio
import io
import sys
import av
import zenoh
import zstd
import cv2
import time
import threading
import numpy as np
from foxglove.schemas import Timestamp, CompressedVideo, PointsAnnotation, Point2, Color, PointsAnnotationType, ImageAnnotations
from edgefirst.schemas.edgefirst_msgs import Detect, Mask
from edgefirst.schemas.foxglove_msgs import CompressedVideo as efcv
import foxglove

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
    
def h264_worker(msg, frame_storage):
    frame_storage.set(960, 544)
    vid = efcv.deserialize(msg.payload.to_bytes())
    foxglove.log(
        "/camera",
        CompressedVideo(
            timestamp=Timestamp(vid.timestamp.sec, vid.timestamp.nanosec),
            frame_id=vid.frame_id,
            data= bytes(vid.data),
            format = vid.format,
        )
    )
    
async def h264_handler(drain, frame_storage):
    while True:
        msg = await drain.get_latest()
        thread = threading.Thread(target=h264_worker, args=[msg, frame_storage])
        thread.start()
        
        while thread.is_alive():
            await asyncio.sleep(0.001)
        thread.join()

def boxes2d_worker(msg, frame_size):
    detection = Detect.deserialize(msg.payload.to_bytes())
    centers = []
    sizes = []
    labels = []
    points = []
    for box in detection.boxes:
        tl_point = Point2(x=(box.center_x - box.width / 2) * frame_size[0], y=(box.center_y - box.height / 2) * frame_size[1])
        tr_point = Point2(x=(box.center_x + box.width / 2) * frame_size[0], y=(box.center_y - box.height / 2) * frame_size[1])
        br_point = Point2(x=(box.center_x + box.width / 2) * frame_size[0], y=(box.center_y + box.height / 2) * frame_size[1])
        bl_point = Point2(x=(box.center_x - box.width / 2) * frame_size[0], y=(box.center_y + box.height / 2) * frame_size[1])
        points.append(
            PointsAnnotation(timestamp=Timestamp.now(),
                             points=[tl_point, tr_point, br_point, bl_point], outline_color=Color(r=0,g=1,b=0,a=1),
                             thickness=3, type=PointsAnnotationType.LineLoop)
        )
        centers.append((box.center_x, box.center_y))
        sizes.append((box.width, box.height))
        labels.append(box.label)
    
    foxglove.log("/camera/boxes", ImageAnnotations(points=points))

async def boxes2d_handler(drain, frame_storage):
    _ = await frame_storage.get()
    print(frame_storage._size)
    while True:
        msg = await drain.get_latest()
        frame_size = await frame_storage.get()
        thread = threading.Thread(target=boxes2d_worker, args=[msg, frame_size])
        thread.start()
        
        while thread.is_alive():
            await asyncio.sleep(0.001)
        thread.join()

# def mask_worker(msg, frame_size, remote):
#     mask = Mask.deserialize(msg.payload.to_bytes())
#     if remote:
#         decoded_array = zstd.decompress(bytes(mask.mask))
#         np_arr = np.frombuffer(decoded_array, np.uint8).reshape(mask.height, mask.width, -1)
#     else:
#         np_arr = np.asarray(mask.mask, dtype=np.uint8)
#         np_arr = np.reshape(np_arr, [mask.height, mask.width, -1])
#     np_arr = cv2.resize(np_arr, frame_size)
#     np_arr = np.argmax(np_arr, axis=2)
    
#     rr.log("/camera/mask", rr.SegmentationImage(np_arr))


# async def mask_handler(drain, frame_storage, remote):
#     _ = await frame_storage.get()
#     rr.log("/", rr.AnnotationContext([(0, "background", (0, 0, 0, 0)), (1, "person", (0, 255, 0))]))
#     while True:
#         msg = await drain.get_latest()
#         frame_size = await frame_storage.get()
#         thread = threading.Thread(target=mask_worker, args=[msg, frame_size, remote])
#         thread.start()
        
#         while thread.is_alive():
#             await asyncio.sleep(0.001)
#         thread.join()

    
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
    boxes_drain = MessageDrain(loop)
    # mask_drain = MessageDrain(loop)
    frame_size_storage = FrameSize()

    session.declare_subscriber('rt/camera/h264', h264_drain.callback)
    session.declare_subscriber('rt/model/boxes2d', boxes_drain.callback)
    # if args.remote:
    #     session.declare_subscriber('rt/model/mask_compressed', mask_drain.callback)
    # else:
    #     session.declare_subscriber('rt/model/mask', mask_drain.callback)
    await asyncio.gather(h264_handler(h264_drain, frame_size_storage), 
                         boxes2d_handler(boxes_drain, frame_size_storage))
                        #  mask_handler(mask_drain, frame_size_storage, args.remote))

    while True:
        asyncio.sleep(0.001)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Camera-Model")
    parser.add_argument('-r', '--remote', type=str, default=None,
                        help="Connect to the remote endpoint instead of local.")
    args = parser.parse_args()

    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == "__main__":
    main()
