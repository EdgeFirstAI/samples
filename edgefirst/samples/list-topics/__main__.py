import time
import zenoh
from argparse import ArgumentParser


if __name__ == "__main__":
    args = ArgumentParser(description="EdgeFirst Samples - List Topics")
    args.add_argument('-c', '--connect', type=str,
                      default='tcp/127.0.0.1:7447',
                      help="Connection endpoint for the zenoh session.")
    args.add_argument('-t', '--time', type=float, default=5,
                      help="Time (sec) to run the subscriber before exiting.")
    args = args.parse_args()

    # Create a Zenoh session using the default configuration plus explicit
    # connection to the local router over TCP at port 7447.  We do this because
    # we currently have scouting disabled to reduce overhead.
    cfg = zenoh.Config()
    cfg.insert_json5("mode", "'client'")
    cfg.insert_json5("connect", '{ "endpoints": ["%s"] }' % args.connect)
    session = zenoh.open(cfg)

    # Keep track of the topics we have already seen to avoid noisy output.
    detected_msgs = set()

    # The listener callback is called whenever a new message is received.
    def listener(msg):
        topic = str(msg.key_expr)
        if topic in detected_msgs:
            return
        detected_msgs.add(topic)

        # Zenoh message encodings use a MIME type format.  The CDR schema is
        # stored after the semicolon in the MIME string.
        schema = str(msg.encoding).split(';', maxsplit=1)[-1]
        print("topic: %s → %s" % (topic, schema))

    try:
        # Declare subscriber that will listen for all the rt/ messages
        sub = session.declare_subscriber('rt/**', listener)

        # The declare_subscriber runs asynchronously, so we need to block the
        # main thread to keep the program running.  We use time.sleep() to do
        # this but an application could have a main control loop here instead.
        time.sleep(args.time)
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        if 'sub' in locals():
            sub.undeclare()
    session.close()
