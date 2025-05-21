import zenoh

from argparse import ArgumentParser
from edgefirst.schemas.edgefirst_msgs import RadarInfo


if __name__ == "__main__":
    args = ArgumentParser(description="EdgeFirst Samples - Radar Info")
    args.add_argument('-r', '--remote', type=str, default=None,
                      help="Connect to the remote endpoint instead of local.")
    args = args.parse_args()

    # Create the default Zenoh configuration and if the remote argument is
    # provided set the mode to client and add the target to the endpoints.
    config = zenoh.Config()
    config.insert_json5("scouting/multicast/interface", "'lo'")
    if args.remote is not None:
        config.insert_json5("mode", "'client'")
        config.insert_json5("connect", '{"endpoints": ["%s"]}' % args.remote)
    session = zenoh.open(config)

    # Create a subscriber for "rt/radar/info"
    subscriber = session.declare_subscriber('rt/radar/info')
    msg = subscriber.recv()

    # deserialize message
    radar_info = RadarInfo.deserialize(msg.payload.to_bytes())
    print("Radar Info:")
    print(f"    Range Mode: {radar_info.frequency_sweep}")
    print(f"   Center Band: {radar_info.center_frequency}")
    print(f"   Sensitivity: {radar_info.detection_sensitivity}")
    print(f"  Range Toggle: {radar_info.range_toggle}")
