use clap::Parser as _;
use edgefirst_samples::Args;
use edgefirst_schemas::sensor_msgs::Image;
use std::{error::Error, sync::Arc};
use tokio::{sync::Mutex, task};
use zenoh::{handlers::FifoChannelHandler, pubsub::Subscriber, sample::Sample};

async fn lidar_depth_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>,
    rr: Arc<Mutex<rerun::RecordingStream>>,
) {
    while let Ok(msg) = sub.recv_async().await {
        let depth = match cdr::deserialize::<Image>(&msg.payload().to_bytes()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize lidar depth: {:?}", e);
                continue; // skip this message and continue
            }
        };

        // Process depth image
        assert_eq!(depth.encoding, "mono16");
        let u16_from_bytes = if depth.is_bigendian > 0 {
            u16::from_be_bytes
        } else {
            u16::from_le_bytes
        };
        let pixels: Vec<u16> = depth
            .data
            .chunks_exact(2)
            .map(|a| u16_from_bytes([a[0], a[1]]))
            .collect();
        let img: Vec<_> = pixels.iter().map(|f| (f / 256) as u8).collect();
        let img = rerun::Image::from_l8(img, [depth.width, depth.height]);

        let rr_guard = rr.lock().await;
        let _ = match rr_guard.log("lidar/depth", &img) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to log lidar depth: {:?}", e);
                continue; // skip this message and continue
            }
        };
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    let (rr, _serve_guard) = args.rerun.init("lidar-depth")?;
    let rr = Arc::new(Mutex::new(rr));

    let sub = session.declare_subscriber("rt/lidar/depth").await.unwrap();
    let rr_clone = rr.clone();
    task::spawn(lidar_depth_handler(sub, rr_clone));

    // Rerun setup
    loop {
        
    }
}
