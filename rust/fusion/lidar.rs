use clap::Parser;
use edgefirst_samples::Args;
use edgefirst_schemas::{decode_pcd, sensor_msgs::PointCloud2};
use rerun::{Color, Points3D, Position3D};
use std::{error::Error, sync::Arc};
use tokio::{sync::Mutex, task};
use zenoh::{handlers::FifoChannelHandler, pubsub::Subscriber, sample::Sample};

///    This demo requires lidar output to be enabled on `fusion` to work.
///    By default the rt/fusion/lidar output is not enabled for `fusion`.
///    To enable it, configure LIDAR_OUTPUT_TOPIC="rt/fusion/lidar" or set
///    command line argument --lidar-output-topic=rt/fusion/lidar

async fn fusion_lidar_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>,
    rr: Arc<Mutex<rerun::RecordingStream>>,
) {
    while let Ok(msg) = sub.recv_async().await {
        let pcd = match cdr::deserialize::<PointCloud2>(&msg.payload().to_bytes()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize fusion_lidar: {:?}", e);
                continue; // skip this message and continue
            }
        };
        let points = decode_pcd(&pcd);
        let max_class = points
            .iter()
            .map(|x| x.fields["vision_class"] as isize)
            .max()
            .unwrap_or(1)
            .max(1);

        let rr_points = Points3D::new(
            points
                .iter()
                .map(|p| Position3D::new(p.x as f32, p.y as f32, p.z as f32)),
        )
        .with_colors(points.iter().map(|p| {
            let (r, g, b) = colorous::TURBO
                .eval_continuous(p.fields["vision_class"] / max_class as f64)
                .as_tuple();
            Color::from_rgb(r, g, b)
        }));
        let rr_guard = rr.lock().await;
        let _ = match rr_guard.log("fusion/lidar", &rr_points) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to log fusion lidar: {:?}", e);
                continue; // skip this message and continue
            }
        };
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    let (rr, _serve_guard) = args.rerun.init("fusion-lidar")?;
    let rr = Arc::new(Mutex::new(rr));

    let sub = session.declare_subscriber("rt/fusion/lidar").await.unwrap();
    let rr_clone = rr.clone();
    task::spawn(fusion_lidar_handler(sub, rr_clone));

    // Rerun setup
    loop {
        
    }
}
