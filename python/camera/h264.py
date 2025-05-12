import zenoh
from edgefirst.schemas.foxglove_msgs import CompressedVideo
import rerun as rr
from argparse import ArgumentParser
import sys
import av
import io


def main():
    args = ArgumentParser(description="EdgeFirst Samples - H264")
    args.add_argument('-r', '--remote', type=str, default=None,
                      help="Connect to a Zenoh router rather than local.")
    rr.script_add_args(args)
    args = args.parse_args()

    rr.script_setup(args, "h264")

    # Create the default Zenoh configuration and if the connect argument is
    # provided set the mode to client and add the target to the endpoints.
    config = zenoh.Config()
    if args.remote is not None:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", '{"endpoints": ["%s"]}' % args.remote)
    session = zenoh.open(config)

    # Create a subscriber for "rt/camera/h264"
    subscriber = session.declare_subscriber('rt/camera/h264')
    raw_data = io.BytesIO()
    container = av.open(raw_data, format='h264', mode='r')
    frame_position = 0

    while True:
        msg = subscriber.recv()
        raw_data.write(msg.payload.to_bytes())
        raw_data.seek(frame_position)
        for packet in container.demux():
            try:
                if packet.size == 0:  # Skip empty packets
                    continue
                frame_position += packet.size  # Update frame position
                for frame in packet.decode():  # Decode video frames
                    # Convert frame to numpy array
                    frame_array = frame.to_ndarray(format='rgb24')
                    rr.log('image', rr.Image(frame_array))
            except Exception as e:  # Handle exceptions
                continue  # Continue processing next packets


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
