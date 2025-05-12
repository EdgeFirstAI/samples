use clap::Parser;
use edgefirst_schemas::{decode_pcd, sensor_msgs::PointCloud2};
use rerun::{Color, Points3D, Position3D};
use std::{error::Error, path::PathBuf, time::Instant};
use zenoh::Config;
#[derive(Parser, Debug, Clone)]
struct Args {
    /// Time in seconds to run command before exiting.
    #[arg(short, long)]
    pub timeout: Option<u64>,

    /// Connect to a Zenoh router rather than peer mode.
    #[arg(short, long)]
    connect: Option<String>,

    /// Rerun file
    #[arg(short, long)]
    rerun: Option<PathBuf>,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();

    let rec = rerun::RecordingStreamBuilder::new("radar/clusters Example")
        .save(args.rerun.unwrap_or("radar-clusters.rrd".into()))?;

    // Create the default Zenoh configuration and if the connect argument is
    // provided set the mode to client and add the target to the endpoints.
    let mut config = Config::default();
    if let Some(connect) = args.connect {
        let post_connect = format!("['{connect}']");
        config.insert_json5("mode", "'client'").unwrap();
        config
            .insert_json5("connect/endpoints", &post_connect)
            .unwrap();
    }
    let session = zenoh::open(config).await.unwrap();

    // Create a subscriber for "rt/radar/clusters"
    let subscriber = session
        .declare_subscriber("rt/radar/clusters")
        .await
        .unwrap();

    let start = Instant::now();

    while let Ok(msg) = subscriber.recv() {
        if let Some(timeout) = args.timeout {
            if start.elapsed().as_secs() >= timeout {
                break;
            }
        }
        let pcd: PointCloud2 = cdr::deserialize(&msg.payload().to_bytes())?;
        let points = decode_pcd(&pcd);
        let clustered_points: Vec<_> = points.iter().filter(|x| x.id > 0).collect();
        let max_cluster_id = clustered_points
            .iter()
            .map(|x| x.id)
            .max()
            .unwrap_or(1)
            .max(1);
        println!(
            "Recieved {} radar points. {} are clustered",
            points.len(),
            clustered_points.len(),
        );

        let rr_points = Points3D::new(
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
        let _ = rec.log("radar/clusters", &rr_points);
    }

    Ok(())
}
