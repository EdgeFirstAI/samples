use clap::Parser;
use edgefirst_schemas::{decode_pcd, sensor_msgs::PointCloud2};
use rerun::{Points3D, Position3D};
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

    let rec = rerun::RecordingStreamBuilder::new("radar/targets Example")
        .save(args.rerun.unwrap_or("radar-targets.rrd".into()))?;

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

    // Create a subscriber for "rt/radar/targets"
    let subscriber = session
        .declare_subscriber("rt/radar/targets")
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
        let min_x = points.iter().map(|p| p.x).fold(f64::INFINITY, f64::min);
        let max_x = points.iter().map(|p| p.x).fold(f64::NEG_INFINITY, f64::max);

        let min_y = points.iter().map(|p| p.y).fold(f64::INFINITY, f64::min);
        let max_y = points.iter().map(|p| p.y).fold(f64::NEG_INFINITY, f64::max);

        let min_z = points.iter().map(|p| p.z).fold(f64::INFINITY, f64::min);
        let max_z = points.iter().map(|p| p.z).fold(f64::NEG_INFINITY, f64::max);

        let min_speed = points
            .iter()
            .map(|p| *p.fields.get("speed").unwrap())
            .fold(f64::INFINITY, f64::min);
        let max_speed = points
            .iter()
            .map(|p| *p.fields.get("speed").unwrap())
            .fold(f64::NEG_INFINITY, f64::max);

        println!(
            "Recieved {} radar points. Values: x: [{min_x:.2}, {max_x:.2}]\ty: [{min_y:.2}, {max_y:.2}]\tz: [{min_z:.2}, {max_z:.2}]\tspeed: [{min_speed:.2}, {max_speed:.2}]",
            points.len(),
        );

        let rr_points = Points3D::new(
            points
                .iter()
                .map(|p| Position3D::new(p.x as f32, p.y as f32, p.z as f32)),
        );
        let _ = rec.log("radar/targets", &rr_points);
    }

    Ok(())
}
