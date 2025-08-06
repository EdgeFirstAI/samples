use clap::Parser as _;
use edgefirst_samples::Args;
use edgefirst_schemas::sensor_msgs::NavSatFix;
use std::{error::Error, sync::Arc};
use tokio::{sync::Mutex, task};
use zenoh::{handlers::FifoChannelHandler, pubsub::Subscriber, sample::Sample};

async fn gps_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>,
    rr: Arc<Mutex<rerun::RecordingStream>>,
) {
    while let Ok(msg) = sub.recv_async().await {
        let gps = match cdr::deserialize::<NavSatFix>(&msg.payload().to_bytes()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize gps: {e:?}");
                continue; // skip this message and continue
            }
        };

        let rr_guard = rr.lock().await;
        match rr_guard.log(
            "CurrentLoc",
            &rerun::GeoPoints::from_lat_lon([(gps.latitude, gps.longitude)]),
        ) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to log gps: {e:?}");
                continue; // skip this message and continue
            }
        };
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    let (rr, _serve_guard) = args.rerun.init("gps")?;
    let rr = Arc::new(Mutex::new(rr));

    let sub = session.declare_subscriber("rt/gps").await.unwrap();
    let rr_clone = rr.clone();
    task::spawn(gps_handler(sub, rr_clone));

    // Rerun setup
    loop {}
}
