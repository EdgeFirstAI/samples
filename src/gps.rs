use clap::Parser;
use edgefirst_schemas::sensor_msgs::{NavSatFix};
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

    // Create a subscriber for "rt/gps"
    let subscriber = session
        .declare_subscriber("rt/gps")
        .await
        .unwrap();

    let start = Instant::now();

    while let Ok(msg) = subscriber.recv() {
        if let Some(timeout) = args.timeout {
            if start.elapsed().as_secs() >= timeout {
                break;
            }
        }
        let gps: NavSatFix = cdr::deserialize(&msg.payload().to_bytes())?;
        println!(
            "Latitude: {} Longitude: {}",
            gps.latitude,
            gps.longitude,
        );
    }

    Ok(())
}

// fn decode_gps(gps: &NavSatFix) -> Vec<f64> {
//     let mut lat_long = Vec::new();
//     lat_long.push(gps.latitude);
//     lat_long.push(gps.longitude);
//     lat_long
// }
