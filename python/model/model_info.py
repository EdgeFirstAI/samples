import zenoh
from edgefirst.schemas.edgefirst_msgs import ModelInfo
import rerun as rr
from argparse import ArgumentParser
import sys

def main():
    args = ArgumentParser(description="EdgeFirst Samples - Model Info")
    args.add_argument('-r', '--remote', type=str, default=None,
                      help="Connect to a Zenoh router rather than local.")
    rr.script_add_args(args)
    args = args.parse_args()

    rr.script_setup(args, "model info")

    # Create the default Zenoh configuration and if the connect argument is
    # provided set the mode to client and add the target to the endpoints.
    config = zenoh.Config()
    if args.remote is not None:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", '{"endpoints": ["%s"]}' % args.remote)
    session = zenoh.open(config)

    # Create a subscriber for "rt/model/info"
    subscriber = session.declare_subscriber('rt/model/info')

    while True:
        msg = subscriber.recv()
        info = ModelInfo.deserialize(msg.payload.to_bytes())
        m_type = info.model_type
        m_name = info.model_name
        input_shape = info.input_shape  # Input Shape
        input_type = info.input_type  # Input Type
        output_shape = info.output_shape  # Output Shape
        output_type = info.output_type  # Output Type
        rr.log("ModelInfo", rr.TextLog("Model Name: %s Model Type: %s" % (m_name, m_type)))

if __name__ == "__main__":    
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)