use clap::Parser;
use edgefirst_schemas::edgefirst_msgs::RadarCube;
use rerun::{Tensor, external::ndarray::Array};
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

    let rec = rerun::RecordingStreamBuilder::new("radar/cube Example")
        .save(args.rerun.unwrap_or("radar-cube.rrd".into()))?;

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

    // Create a subscriber for "rt/radar/cube"
    let subscriber = session.declare_subscriber("rt/radar/cube").await.unwrap();

    let start = Instant::now();

    while let Ok(msg) = subscriber.recv() {
        if let Some(timeout) = args.timeout {
            if start.elapsed().as_secs() >= timeout {
                break;
            }
        }
        let radar_cube: RadarCube = cdr::deserialize(&msg.payload().to_bytes())?;

        println!("The radar cube has shape: {:?}", radar_cube.shape);

        let cube = scale_radar_cube(&radar_cube.cube);
        let data = Array::<u16, _>::from_shape_vec(
            (
                radar_cube.shape[0] as usize,
                radar_cube.shape[1] as usize,
                radar_cube.shape[2] as usize,
                radar_cube.shape[3] as usize,
            ),
            cube,
        )?;
        let tensor = Tensor::try_from(data)?.with_dim_names(["SEQ", "RANGE", "RX", "DOPPLER"]);
        let _ = rec.log("radar/cube", &tensor);
    }

    Ok(())
}

const FACTOR: f64 = 65535.0 / 2500.0;
fn scale_radar_cube(cube: &[i16]) -> Vec<u16> {
    cube.iter()
        .map(|x| (((x.abs() + 1) as f64).log2() * FACTOR).min(65535.0) as u16)
        .collect()
}
