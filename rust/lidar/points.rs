use clap::Parser as _;
use edgefirst_samples::Args;
use edgefirst_schemas::{decode_pcd, sensor_msgs::PointCloud2};
use rerun::{Points3D, Position3D};
use std::{error::Error, sync::Arc};
use tokio::{sync::Mutex, task};
use zenoh::{handlers::FifoChannelHandler, pubsub::Subscriber, sample::Sample};

async fn lidar_points_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>,
    rr: Arc<Mutex<rerun::RecordingStream>>,
) {
    while let Ok(msg) = sub.recv_async().await {
        let pcd = match cdr::deserialize::<PointCloud2>(&msg.payload().to_bytes()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize lidar points: {:?}", e);
                continue; // skip this message and continue
            }
        };

        let points = decode_pcd(&pcd);
        let points = Points3D::new(
            points
                .iter()
                .map(|p| Position3D::new(p.x as f32, p.y as f32, p.z as f32)),
        );

        let rr_guard = rr.lock().await;
        let _ = match rr_guard.log("lidar/points", &points) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to log lidar points: {:?}", e);
                continue; // skip this message and continue
            }
        };
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    let (rr, _serve_guard) = args.rerun.init("lidar-points")?;
    let rr = Arc::new(Mutex::new(rr));

    let sub = session.declare_subscriber("rt/lidar/points").await.unwrap();
    let rr_clone = rr.clone();
    task::spawn(lidar_points_handler(sub, rr_clone));

    // Rerun setup
    loop {
        
    }
}

