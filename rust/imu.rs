use clap::Parser;
use edgefirst_schemas::sensor_msgs::IMU;
use std::{error::Error, time::Instant};
use zenoh::Config;

#[derive(Parser, Debug, Clone)]
struct Args {
    /// Time in seconds to run command before exiting.
    #[arg(short, long)]
    pub timeout: Option<u64>,

    /// Connect to a Zenoh router rather than peer mode.
    #[arg(short, long)]
    connect: Option<String>,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    // Create the default Zenoh configuration and if the connect argument is
    // provided set the mode to client and add the target to the endpoints.
    let mut config = Config::default();
    if let Some(connect) = args.connect {
        let mut post_connect: String = "['".to_owned();
        post_connect = post_connect + &connect + "']";
        config.insert_json5("mode", "'client'").unwrap();
        config
            .insert_json5("connect/endpoints", &post_connect)
            .unwrap();
    }
    let session = zenoh::open(config).await.unwrap();

    // Create a subscriber for "rt/imu"
    let subscriber = session.declare_subscriber("rt/imu").await.unwrap();

    let start = Instant::now();

    let rec = rerun::RecordingStreamBuilder::new("Imu Example").spawn()?;
    let rr_box =
        rerun::Boxes3D::from_half_sizes([(0.5, 0.5, 0.5)]).with_fill_mode(rerun::FillMode::Solid);
    rec.log("box", &rr_box)?;
    let _ = rec.log("box", &rerun::Transform3D::default().with_axis_length(2.0));

    while let Ok(msg) = subscriber.recv() {
        if let Some(timeout) = args.timeout {
            if start.elapsed().as_secs() >= timeout {
                break;
            }
        }
        let imu: IMU = cdr::deserialize(&msg.payload().to_bytes())?;
        let x = imu.orientation.x as f32;
        let y = imu.orientation.y as f32;
        let z = imu.orientation.z as f32;
        let w = imu.orientation.w as f32;
        // println!("X: {} Y: {} Z: {} W: {}", x, y, z, w);
        let my_quat = rerun::Quaternion([x, y, z, w]);
        let _ = rec.log(
            "box",
            &rerun::Transform3D::default().with_quaternion(my_quat),
        );
    }

    Ok(())
}
