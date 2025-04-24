use clap::Parser;
use edgefirst_schemas::sensor_msgs::Image;
use std::{collections::HashMap, error::Error, time::Instant};
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
        config.insert_json5("mode", "client").unwrap();
        config.insert_json5("connect/endpoints", &connect).unwrap();
    }
    let session = zenoh::open(config).await.unwrap();

    // Create a subscriber for "rt/lidar/depth"
    let subscriber = session.declare_subscriber("rt/lidar/depth").await.unwrap();

    let start = Instant::now();

    while let Ok(msg) = subscriber.recv() {
        if let Some(timeout) = args.timeout {
            if start.elapsed().as_secs() >= timeout {
                break;
            }
        }
        let depth: Image = cdr::deserialize(&msg.payload().to_bytes())?;
        let u16_from_bytes = if depth.is_bigendian > 0 {
            u16::from_be_bytes
        } else {
            u16::from_le_bytes
        };
        assert_eq!(depth.encoding, "mono16");
        let depth_vals: Vec<u16> = depth
            .data
            .chunks_exact(2)
            .map(|a| u16_from_bytes([a[0], a[1]]))
            .collect();
        let min_depth_mm = *depth_vals.iter().min().unwrap();
        let max_depth_mm = *depth_vals.iter().max().unwrap();
        println!(
            "Recieved {}x{} depth image. Depth: [{min_depth_mm}, {max_depth_mm}]",
            depth.width, depth.height
        );
    }

    Ok(())
}
