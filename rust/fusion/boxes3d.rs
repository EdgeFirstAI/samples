use clap::Parser;
use edgefirst_samples::Args;
use edgefirst_schemas::edgefirst_msgs::Detect;
use rerun::Boxes3D;
use std::error::Error;
#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    // Create Rerun logger using the provided parameters
    let (rec, _serve_guard) = args.rerun.init("fusion-boxes3d")?;

    // Create a subscriber for "rt/fusion/boxes3d"
    let subscriber = session
        .declare_subscriber("rt/fusion/boxes3d")
        .await
        .unwrap();

    while let Ok(msg) = subscriber.recv() {
        let det: Detect = cdr::deserialize(&msg.payload().to_bytes())?;
        let boxes = det.boxes;
        println!("Recieved {} 3D boxes.", boxes.len());

        let rr_boxes = Boxes3D::from_centers_and_sizes(
            boxes.iter().map(|b| (b.distance, b.center_x, b.center_y)),
            boxes.iter().map(|b| (b.width, b.width, b.height)),
        );
        let _ = rec.log("fusion/boxes3d", &rr_boxes);
    }

    Ok(())
}
