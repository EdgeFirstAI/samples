from argparse import ArgumentParser
import asyncio
import io
import sys
import av
import zenoh
import zstd
import cv2
import rerun as rr
import rerun.blueprint as rrb
import numpy as np
from edgefirst.schemas.edgefirst_msgs import Detect, Mask

class MessageDrain:
    def __init__(self, loop):
        self._queue = asyncio.Queue()
        self._loop = loop

    def callback(self, msg):
        self._loop.call_soon_threadsafe(self._queue.put_nowait, msg)

    async def read(self):
        return await self._queue.get()

    async def get_latest(self):
        latest = await self._queue.get()
        while not self._queue.empty():
            latest = self._queue.get_nowait()
        return latest

raw_data = io.BytesIO()
container = av.open(raw_data, format='h264', mode='r')
frame_size = []

async def h264_processing(drain):
    global frame_size
    while True:
        msg = await drain.get_latest()
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
                    frame_size = [frame_array.shape[1], frame_array.shape[0]]
                    rr.log('/camera', rr.Image(frame_array))
            except Exception:
                continue


async def boxes2d_processing(drain):
    global frame_size
    while True:
        msg = await drain.get_latest()
        if len(frame_size) != 2:
            await asyncio.sleep(0.001)
            continue

        centers, sizes, labels = [], [], []
        detection = Detect.deserialize(msg.payload.to_bytes())

        for box in detection.boxes:
            centers.append((int(box.center_x * frame_size[0]), int(box.center_y * frame_size[1])))
            sizes.append((int(box.width * frame_size[0]), int(box.height * frame_size[1])))
            labels.append(box.label)

        rr.log("/camera/boxes", rr.Boxes2D(centers=centers, sizes=sizes, labels=labels))


async def mask_processing(drain, remote):
    global frame_size
    while True:
        msg = await drain.get_latest()
        if len(frame_size) != 2:
            await asyncio.sleep(0.001)
            continue

        mask = Mask.deserialize(msg.payload.to_bytes())
        if remote:
            decoded_array = zstd.decompress(bytes(mask.mask))
            np_arr = np.frombuffer(decoded_array, np.uint8).reshape(mask.height, mask.width, -1)
        else:
            np_arr = np.asarray(mask.mask, dtype=np.uint8)
            np_arr = np.reshape(np_arr, [mask.height, mask.width, -1])
        np_arr = cv2.resize(np_arr, frame_size)
        np_arr = np.argmax(np_arr, axis=2)

        rr.log("/", rr.AnnotationContext([(0, "background", (0, 0, 0, 0)), (1, "person", (0, 255, 0))]))
        rr.log("/camera/mask", rr.SegmentationImage(np_arr))


async def main_async(args):
    loop = asyncio.get_running_loop()

    # Setup rerun
    args.memory_limit = 10
    rr.script_setup(args, "camera_radar")

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
    h264_drain = MessageDrain(loop)
    boxes2d_drain = MessageDrain(loop)
    mask_drain = MessageDrain(loop)

    # Declare subscribers
    session.declare_subscriber('rt/camera/h264', h264_drain.callback)
    session.declare_subscriber('rt/model/boxes2d', boxes2d_drain.callback)
    if args.remote:
        session.declare_subscriber('rt/model/mask_compressed', mask_drain.callback)
    else:
        session.declare_subscriber('rt/model/mask', mask_drain.callback)

    # Launch concurrent processing tasks
    await asyncio.gather(
        h264_processing(h264_drain),
        boxes2d_processing(boxes2d_drain),
        mask_processing(mask_drain, args.remote),
    )

def main():
    parser = ArgumentParser(description="EdgeFirst Samples - Camera Model")
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

