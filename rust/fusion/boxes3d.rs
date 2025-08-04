use clap::Parser;
use edgefirst_samples::Args;
use edgefirst_schemas::edgefirst_msgs::Detect;
use rerun::Boxes3D;
use std::{error::Error, sync::Arc};
use tokio::{sync::Mutex, task};
use zenoh::{handlers::FifoChannelHandler, pubsub::Subscriber, sample::Sample};

async fn fusion_boxes3d_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>,
    rr: Arc<Mutex<rerun::RecordingStream>>,
) {
    while let Ok(msg) = sub.recv_async().await {
        let det = match cdr::deserialize::<Detect>(&msg.payload().to_bytes()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize fusion_boxes3d: {e:?}");
                continue; // skip this message and continue
            }
        };
        let boxes = det.boxes;
        // The 3D boxes are in an _optical frame of reference, where x is right, y is down, and z (distance) is forward
        // We will convert them to a normal frame of reference, where x is forward, y is left, and z is up
        let rr_boxes = Boxes3D::from_centers_and_sizes(
            boxes.iter().map(|b| (b.distance, -b.center_x, -b.center_y)),
            boxes.iter().map(|b| (b.width, b.width, b.height)),
        );
        let rr_guard = rr.lock().await;
        match rr_guard.log("fusion/boxes3d", &rr_boxes) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to log fusion boxes3d: {e:?}");
                continue; // skip this message and continue
            }
        };
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    let (rr, _serve_guard) = args.rerun.init("fusion-boxes3d")?;
    let rr = Arc::new(Mutex::new(rr));

    let sub = session
        .declare_subscriber("rt/fusion/boxes3d")
        .await
        .unwrap();
    let rr_clone = rr.clone();
    task::spawn(fusion_boxes3d_handler(sub, rr_clone));

    // Rerun setup
    loop {}
}
