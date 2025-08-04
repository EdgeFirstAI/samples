use clap::Parser as _;
use edgefirst_samples::Args;
use edgefirst_schemas::edgefirst_msgs::RadarInfo;
use std::{error::Error, sync::Arc};
use tokio::{sync::Mutex, task};
use zenoh::{handlers::FifoChannelHandler, pubsub::Subscriber, sample::Sample};

async fn radar_info_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>,
    rr: Arc<Mutex<rerun::RecordingStream>>,
) {
    while let Ok(msg) = sub.recv_async().await {
        let info = match cdr::deserialize::<RadarInfo>(&msg.payload().to_bytes()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize radar info: {e:?}");
                continue; // skip this message and continue
            }
        };

        let text = format!("{info:?}");
        let rr_guard = rr.lock().await;
        match rr_guard.log("radar/info", &rerun::TextLog::new(text)) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to log radar info: {e:?}");
                continue; // skip this message and continue
            }
        };
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    let (rr, _serve_guard) = args.rerun.init("radar-info")?;
    let rr = Arc::new(Mutex::new(rr));

    let sub = session.declare_subscriber("rt/radar/info").await.unwrap();
    let rr_clone = rr.clone();
    task::spawn(radar_info_handler(sub, rr_clone));

    // Rerun setup
    loop {}
}
