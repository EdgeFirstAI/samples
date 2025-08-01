use clap::Parser as _;
use edgefirst_samples::Args;
use edgefirst_schemas::sensor_msgs::Image;
use std::{error::Error, sync::Arc};
use tokio::{sync::Mutex, task};
use zenoh::{handlers::FifoChannelHandler, pubsub::Subscriber, sample::Sample};

async fn lidar_reflect_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>,
    rr: Arc<Mutex<rerun::RecordingStream>>,
) {
    while let Ok(msg) = sub.recv_async().await {
        let reflect = match cdr::deserialize::<Image>(&msg.payload().to_bytes()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize lidar reflect: {:?}", e);
                continue; // skip this message and continue
            }
        };

        // Reflectivity image must be mono8
        assert_eq!(reflect.encoding, "mono8");
        let img = rerun::Image::from_l8(reflect.data, [reflect.width, reflect.height]);

        let rr_guard = rr.lock().await;
        let _ = match rr_guard.log("lidar/reflect", &img) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to log lidar reflect: {:?}", e);
                continue; // skip this message and continue
            }
        };
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    let (rr, _serve_guard) = args.rerun.init("lidar-reflect")?;
    let rr = Arc::new(Mutex::new(rr));

    let sub = session.declare_subscriber("rt/lidar/reflect").await.unwrap();
    let rr_clone = rr.clone();
    task::spawn(lidar_reflect_handler(sub, rr_clone));

    // Rerun setup
    loop {
        
    }
}
