use clap::Parser;
use edgefirst_schemas::edgefirst_msgs::RadarInfo;
use std::{error::Error, time::Instant};
use zenoh::Config;
#[derive(Parser, Debug, Clone)]
struct Args {
    /// Time in seconds to run command before exiting.
    #[arg(short, long)]
    pub timeout: Option<u64>,

    /// Connect to a Zenoh router rather than peer mode.
    #[arg(short, long)]
    connect: Option<String>,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    // Create the default Zenoh configuration and if the connect argument is
    // provided set the mode to client and add the target to the endpoints.
    let mut config = Config::default();
    if let Some(connect) = args.connect {
        config.insert_json5("mode", "client").unwrap();
        config.insert_json5("connect/endpoints", &connect).unwrap();
    }
    let session = zenoh::open(config).await.unwrap();

    // Create a subscriber for "rt/radar/info"
    let subscriber = session.declare_subscriber("rt/radar/info").await.unwrap();

    let start = Instant::now();

    while let Ok(msg) = subscriber.recv() {
        if let Some(timeout) = args.timeout {
            if start.elapsed().as_secs() >= timeout {
                break;
            }
        }
        let radar_info: RadarInfo = cdr::deserialize(&msg.payload().to_bytes())?;

        println!(
            "The radar configuration is: center frequency: {}   frequency sweep: {}   range toggle: {}   detection sensitivity: {}   sending cube: {}",
            radar_info.center_frequency,
            radar_info.frequency_sweep,
            radar_info.range_toggle,
            radar_info.detection_sensitivity,
            radar_info.cube
        )
    }

    Ok(())
}
