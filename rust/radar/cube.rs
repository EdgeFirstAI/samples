use clap::Parser as _;
use edgefirst_samples::Args;
use edgefirst_schemas::edgefirst_msgs::RadarCube;
use rerun::{Tensor, external::ndarray::Array};
use std::{error::Error, sync::Arc};
use tokio::{sync::Mutex, task};
use zenoh::{handlers::FifoChannelHandler, pubsub::Subscriber, sample::Sample};

async fn radar_cube_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>,
    rr: Arc<Mutex<rerun::RecordingStream>>,
) {
    while let Ok(msg) = sub.recv_async().await {
        let radar = match cdr::deserialize::<RadarCube>(&msg.payload().to_bytes()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize radar cube: {:?}", e);
                continue; // skip this message and continue
            }
        };

        let shape = radar.shape.iter().map(|&x| x as usize).collect::<Vec<_>>();
        let values = radar.cube.iter().map(|x| x.abs() as u16).collect::<Vec<_>>();
        let data = match Array::<u16, _>::from_shape_vec(shape, values) {
            Ok(arr) => arr,
            Err(e) => {
                eprintln!("Failed to create ndarray from radar cube: {:?}", e);
                continue; // skip this message and continue
            }
        };

        let tensor = match Tensor::try_from(data) {
            Ok(t) => t.with_dim_names(["SEQ", "RANGE", "RX", "DOPPLER"]),
            Err(e) => {
                eprintln!("Failed to convert ndarray to Tensor: {:?}", e);
                continue;
            }
        };

        let rr_guard = rr.lock().await;
        let _ = match rr_guard.log("radar/cube", &tensor) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to log radar cube: {:?}", e);
                continue; // skip this message and continue
            }
        };
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    let (rr, _serve_guard) = args.rerun.init("radar-cube")?;
    let rr = Arc::new(Mutex::new(rr));

    let sub = session.declare_subscriber("rt/radar/cube").await.unwrap();
    let rr_clone = rr.clone();
    task::spawn(radar_cube_handler(sub, rr_clone));

    // Rerun setup
    loop {
        
    }
}
