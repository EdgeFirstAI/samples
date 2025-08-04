use clap::Parser as _;
use edgefirst_samples::Args;
use edgefirst_schemas::{decode_pcd, sensor_msgs::PointCloud2};
use rerun::{Color, Points3D, Position3D};
use std::{error::Error, sync::Arc};
use tokio::{sync::Mutex, task};
use zenoh::{handlers::FifoChannelHandler, pubsub::Subscriber, sample::Sample};

async fn lidar_clusters_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>,
    rr: Arc<Mutex<rerun::RecordingStream>>,
) {
    while let Ok(msg) = sub.recv_async().await {
        let pcd = match cdr::deserialize::<PointCloud2>(&msg.payload().to_bytes()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize lidar clusters: {e:?}");
                continue; // skip this message and continue
            }
        };

        let points = decode_pcd(&pcd);
        let clustered_points: Vec<_> = points.iter().filter(|x| x.id > 0).collect();
        let max_cluster_id = clustered_points
            .iter()
            .map(|x| x.id)
            .max()
            .unwrap_or(1)
            .max(1);

        let points = Points3D::new(
            clustered_points
                .iter()
                .map(|p| Position3D::new(p.x as f32, p.y as f32, p.z as f32)),
        )
        .with_colors(clustered_points.iter().map(|p| {
            let (r, g, b) = colorous::TURBO
                .eval_continuous(p.id as f64 / max_cluster_id as f64)
                .as_tuple();
            Color::from_rgb(r, g, b)
        }));

        let rr_guard = rr.lock().await;
        match rr_guard.log("lidar/clusters", &points) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to log lidar clusters: {e:?}");
                continue; // skip this message and continue
            }
        };
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    let (rr, _serve_guard) = args.rerun.init("lidar-clusters")?;
    let rr = Arc::new(Mutex::new(rr));

    let sub = session
        .declare_subscriber("rt/lidar/clusters")
        .await
        .unwrap();
    let rr_clone = rr.clone();
    task::spawn(lidar_clusters_handler(sub, rr_clone));

    // Rerun setup
    loop {}
}
