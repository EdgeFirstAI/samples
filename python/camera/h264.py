import zenoh
import rerun as rr
from argparse import ArgumentParser
import sys
import av
import io
import time

raw_data = io.BytesIO()
container = av.open(raw_data, format='h264', mode='r')
received_messages = []

def h264_callback(msg):
    global received_messages
    received_messages.append(msg.payload.to_bytes())

def main():
    global received_messages
    args = ArgumentParser(description="EdgeFirst Samples - H264")
    args.add_argument('-r', '--remote', type=str, default=None,
                      help="Connect to a Zenoh router rather than local.")
    rr.script_add_args(args)
    args = args.parse_args()

    rr.script_setup(args, "h264")

    # Create the default Zenoh configuration and if the connect argument is
    # provided set the mode to client and add the target to the endpoints.
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    if args.remote is not None:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", '{"endpoints": ["%s"]}' % args.remote)
    session = zenoh.open(config)

    # Create a subscriber for "rt/camera/h264"
    subscriber = session.declare_subscriber('rt/camera/h264', h264_callback)
    raw_data = io.BytesIO()
    container = av.open(raw_data, format='h264', mode='r')

    while True:
        if not received_messages:
            time.sleep(0.001)
            continue
        raw_data.write(received_messages.pop())
        # print("Skipping %d frames" % len(received_messages))
        received_messages = []
        raw_data.seek(0)
        for packet in container.demux():
            try:
                if packet.size == 0:  # Skip empty packets
                    continue
                raw_data.seek(0)
                raw_data.truncate(0)
                for frame in packet.decode():  # Decode video frames
                    frame_array = frame.to_ndarray(format='rgb24')  # Convert frame to numpy array
                    rr.log('image', rr.Image(frame_array))
            except Exception:  # Handle exceptions
                continue  # Continue processing next packets
              

if __name__ == "__main__":    
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)