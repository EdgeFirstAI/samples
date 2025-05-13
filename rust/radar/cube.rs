use clap::Parser as _;
use edgefirst_samples::Args;
use edgefirst_schemas::edgefirst_msgs::RadarCube;
use rerun::{Tensor, external::ndarray::Array};
use std::error::Error;

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    // Create a subscriber for "rt/radar/cube"
    let subscriber = session.declare_subscriber("rt/radar/cube").await.unwrap();

    // Create Rerun logger using the provided parameters
    let (rr, _serve_guard) = args.rerun.init("radar-cube")?;

    while let Ok(msg) = subscriber.recv() {
        let radar: RadarCube = cdr::deserialize(&msg.payload().to_bytes())?;
        let data = Array::<u16, _>::from_shape_vec(
            radar.shape.iter().map(|&x| x as usize).collect::<Vec<_>>(),
            radar
                .cube
                .iter()
                .map(|x| x.abs() as u16)
                .collect::<Vec<_>>(),
        )?;
        let tensor = Tensor::try_from(data)?.with_dim_names(["SEQ", "RANGE", "RX", "DOPPLER"]);
        rr.log("radar/cube", &tensor)?;
    }

    Ok(())
}
