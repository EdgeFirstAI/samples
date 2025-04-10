import zenoh
from argparse import ArgumentParser
from time import time


if __name__ == "__main__":
    args = ArgumentParser(description="EdgeFirst Samples - List Topics")
    args.add_argument('-c', '--connect', type=str, default=None,
                      help="Connect to a Zenoh router rather than peer mode.")
    args.add_argument('-t', '--time', type=float, default=None,
                      help="Time in seconds to run command before exiting.")
    args = args.parse_args()

    # Create the default Zenoh configuration and if the connect argument is
    # provided set the mode to client and add the target to the endpoints.
    config = zenoh.Config()
    if args.connect is not None:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", '{"endpoints": ["%s"]}' % args.connect)
    session = zenoh.open(config)

    # Create a subscriber for all topics matching the pattern "rt/**"
    subscriber = session.declare_subscriber('rt/**')

    # Keep a list of discovered topics to avoid noise from duplicates
    topics = set()
    start = time()

    while True:
        if args.time is not None and time() - start >= args.time:
            break
        msg = subscriber.recv()

        # Ignore message if the topic is known otherwise save the topic
        topic = str(msg.key_expr)
        if topic in topics:
            continue
        topics.add(topic)

        # Capture the message encoding MIME type then split on the first ';'
        # to get the schema.
        schema = str(msg.encoding).split(';', maxsplit=1)[-1]
        print("topic: %s → %s" % (topic, schema))
