use clap::Parser as _;
use edgefirst_samples::Args;
use edgefirst_schemas::sensor_msgs::IMU;
use std::{error::Error, sync::Arc};
use tokio::{sync::Mutex, task};
use zenoh::{handlers::FifoChannelHandler, pubsub::Subscriber, sample::Sample};

async fn imu_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>,
    rr: Arc<Mutex<rerun::RecordingStream>>,
) {
    while let Ok(msg) = sub.recv_async().await {
        let imu = match cdr::deserialize::<IMU>(&msg.payload().to_bytes()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize imu: {e:?}");
                continue; // skip this message and continue
            }
        };

        let x = imu.orientation.x as f32;
        let y = imu.orientation.y as f32;
        let z = imu.orientation.z as f32;
        let w = imu.orientation.w as f32;
        let pose = rerun::Quaternion([x, y, z, w]);

        let rr_guard = rr.lock().await;
        match rr_guard.log("imu", &rerun::Transform3D::default().with_quaternion(pose)) {
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

    let (rr, _serve_guard) = args.rerun.init("imu")?;
    let rr_box =
        rerun::Boxes3D::from_half_sizes([(0.5, 0.5, 0.5)]).with_fill_mode(rerun::FillMode::Solid);
    rr.log("box", &rr_box)?;
    rr.log("box", &rerun::Transform3D::default().with_axis_length(2.0))?;
    let rr = Arc::new(Mutex::new(rr));

    let sub = session.declare_subscriber("rt/imu").await.unwrap();
    let rr_clone = rr.clone();
    task::spawn(imu_handler(sub, rr_clone));

    // Rerun setup
    loop {}
}
