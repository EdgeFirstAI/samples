use clap::Parser as _;
use edgefirst_samples::Args;
use edgefirst_schemas::sensor_msgs::NavSatFix;
use std::error::Error;

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    // Create a subscriber for "rt/gps"
    let subscriber = session.declare_subscriber("rt/gps").await.unwrap();

    // Create Rerun logger using the provided parameters
    let (rr, _serve_guard) = args.rerun.init("gps")?;

    while let Ok(msg) = subscriber.recv() {
        let gps: NavSatFix = cdr::deserialize(&msg.payload().to_bytes())?;
        rr.log(
            "CurrentLoc",
            &rerun::GeoPoints::from_lat_lon([(gps.latitude, gps.longitude)]),
        )?;
    }

    Ok(())
}
