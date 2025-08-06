use clap::Parser as _;
use edgefirst_samples::Args;
use edgefirst_schemas::sensor_msgs::CameraInfo;
use std::{error::Error, sync::Arc};
use tokio::{sync::Mutex, task};
use zenoh::{handlers::FifoChannelHandler, pubsub::Subscriber, sample::Sample};

async fn camera_info_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>,
    rr: Arc<Mutex<rerun::RecordingStream>>,
) {
    while let Ok(msg) = sub.recv_async().await {
        let info = match cdr::deserialize::<CameraInfo>(&msg.payload().to_bytes()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize camera info: {e:?}");
                continue;
            }
        };
        let width = info.width;
        let height = info.height;
        let text = "Camera Width: ".to_owned()
            + &width.to_string()
            + " Camera Height: "
            + &height.to_string();
        let rr_guard = rr.lock().await;
        if let Err(e) = rr_guard.log("CameraInfo", &rerun::TextLog::new(text)) {
            eprintln!("Failed to log camera info: {e:?}");
        }
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    let (rr, _serve_guard) = args.rerun.init("camera-info")?;
    let rr = Arc::new(Mutex::new(rr));

    let sub = session.declare_subscriber("rt/camera/info").await.unwrap();
    let rr_clone = rr.clone();
    task::spawn(camera_info_handler(sub, rr_clone));

    // Rerun setup
    loop {}
}
