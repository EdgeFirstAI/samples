use clap::Parser;
use edgefirst_schemas::sensor_msgs::NavSatFix;
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
        let mut post_connect: String = "['".to_owned();
        post_connect = post_connect + &connect + "']";
        config.insert_json5("mode", "'client'").unwrap();
        config
            .insert_json5("connect/endpoints", &post_connect)
            .unwrap();
    }
    let session = zenoh::open(config).await.unwrap();

    // Create a subscriber for "rt/gps"
    let subscriber = session.declare_subscriber("rt/gps").await.unwrap();

    let start = Instant::now();

    let rec = rerun::RecordingStreamBuilder::new("GPS Example").spawn()?;

    while let Ok(msg) = subscriber.recv() {
        if let Some(timeout) = args.timeout {
            if start.elapsed().as_secs() >= timeout {
                break;
            }
        }
        let gps: NavSatFix = cdr::deserialize(&msg.payload().to_bytes())?;
        let lat = gps.latitude;
        let long = gps.longitude;
        // println!("Latitude: {} Longitude: {}",lat, long);
        let _ = rec.log("CurrentLoc", &rerun::GeoPoints::from_lat_lon([(lat, long)]));
    }

    Ok(())
}
