use clap::Parser;
use edgefirst_schemas::sensor_msgs::Image;
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
        config.insert_json5("mode", "client").unwrap();
        config.insert_json5("connect/endpoints", &connect).unwrap();
    }
    let session = zenoh::open(config).await.unwrap();

    // Create a subscriber for "rt/lidar/reflect"
    let subscriber = session
        .declare_subscriber("rt/lidar/reflect")
        .await
        .unwrap();

    let start = Instant::now();

    while let Ok(msg) = subscriber.recv() {
        if let Some(timeout) = args.timeout {
            if start.elapsed().as_secs() >= timeout {
                break;
            }
        }
        let reflect: Image = cdr::deserialize(&msg.payload().to_bytes())?;

        // Process reflect image
        assert_eq!(reflect.encoding, "mono8");

        let reflect_vals = reflect.data.clone();

        let min_reflect_mm = *reflect_vals.iter().min().unwrap();
        let max_reflect_mm = *reflect_vals.iter().max().unwrap();
        println!(
            "Recieved {}x{} reflect image. reflect: [{min_reflect_mm}, {max_reflect_mm}]",
            reflect.width, reflect.height
        );
    }

    Ok(())
}
