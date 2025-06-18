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
import rerun as rr
import rerun.blueprint as rrb
import numpy as np
from edgefirst.schemas.edgefirst_msgs import Detect, Mask

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
                rr.log('/camera', rr.Image(frame_array))
        except Exception:
            continue
    
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
    centers, sizes, labels, colors = [], [], [], []
    for box in detection.boxes:
        if box.track.id and box.track.id not in boxes_tracked:
            boxes_tracked[box.track.id] = [box.label + ": " + box.track.id[:6], list(np.random.choice(range(256), size=3))]
        if box.track.id:
            colors.append(boxes_tracked[box.track.id][1])
            labels.append(boxes_tracked[box.track.id][0])
        else:
            colors.append([0,255,0])
            labels.append(box.label)
        centers.append((int(box.center_x * frame_size[0]), int(box.center_y * frame_size[1])))
        sizes.append((int(box.width * frame_size[0]), int(box.height * frame_size[1])))
    rr.log("/camera/boxes", rr.Boxes2D(centers=centers, sizes=sizes, labels=labels, colors=colors))

async def boxes2d_handler(drain, frame_storage):
    boxes_tracked = {}
    frame_size = await frame_storage.get()
    while True:
        msg = await drain.get_latest()
        frame_size = await frame_storage.get()
        thread = threading.Thread(target=boxes2d_worker, args=[msg, boxes_tracked, frame_size])
        thread.start()
        
        while thread.is_alive():
            await asyncio.sleep(0.001)
        thread.join()

def mask_worker(msg, frame_size, remote):
    mask = Mask.deserialize(msg.payload.to_bytes())
    if remote:
        decoded_array = zstd.decompress(bytes(mask.mask))
        np_arr = np.frombuffer(decoded_array, np.uint8).reshape(mask.height, mask.width, -1)
    else:
        np_arr = np.asarray(mask.mask, dtype=np.uint8)
        np_arr = np.reshape(np_arr, [mask.height, mask.width, -1])
    np_arr = cv2.resize(np_arr, frame_size)
    np_arr = np.argmax(np_arr, axis=2)
    
    rr.log("/camera/mask", rr.SegmentationImage(np_arr))


async def mask_handler(drain, frame_storage, remote):
    frame_size = await frame_storage.get()
    rr.log("/", rr.AnnotationContext([(0, "background", (0, 0, 0, 0)), (1, "person", (0, 255, 0))]))
    while True:
        msg = await drain.get_latest()
        frame_size = await frame_storage.get()
        thread = threading.Thread(target=mask_worker, args=[msg, frame_size, remote])
        thread.start()
        
        while thread.is_alive():
            await asyncio.sleep(0.001)
        thread.join()

    
async def main_async(args):
    # Setup rerun
    # args.memory_limit = 10
    rr.script_setup(args, "camera-model")

    blueprint = rrb.Blueprint(
        rrb.Grid(contents=[
            rrb.Spatial2DView(origin="/camera", name="Camera Feed")
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

    # Create drains
    loop = asyncio.get_running_loop()
    h264_drain = MessageDrain(loop)
    boxes_drain = MessageDrain(loop)
    mask_drain = MessageDrain(loop)
    frame_size_storage = FrameSize()

    session.declare_subscriber('rt/camera/h264', h264_drain.callback)
    session.declare_subscriber('rt/model/boxes2d', boxes_drain.callback)
    if args.remote:
        session.declare_subscriber('rt/model/mask_compressed', mask_drain.callback)
    else:
        session.declare_subscriber('rt/model/mask', mask_drain.callback)
    await asyncio.gather(h264_handler(h264_drain, frame_size_storage), 
                         boxes2d_handler(boxes_drain, frame_size_storage),
                         mask_handler(mask_drain, frame_size_storage, args.remote))

    while True:
        time.sleep(0.001)


def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Camera-Model")
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
