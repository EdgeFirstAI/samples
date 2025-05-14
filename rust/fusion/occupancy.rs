use clap::Parser;
use edgefirst_samples::Args;
use edgefirst_schemas::{decode_pcd, sensor_msgs::PointCloud2};
use rerun::{Color, Points3D, Position3D};
use std::error::Error;

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    // Create Rerun logger using the provided parameters
    let (rec, _serve_guard) = args.rerun.init("fusion-occupancy")?;

    // Create a subscriber for "rt/fusion/occupancy"
    let subscriber = session
        .declare_subscriber("rt/fusion/occupancy")
        .await
        .unwrap();

    while let Ok(msg) = subscriber.recv() {
        let pcd: PointCloud2 = cdr::deserialize(&msg.payload().to_bytes())?;
        let points = decode_pcd(&pcd);
        let max_class = points
            .iter()
            .map(|x| x.fields["vision_class"] as isize)
            .max()
            .unwrap_or(1)
            .max(1);
        let points_with_vision_class: Vec<_> = points
            .iter()
            .filter(|x| x.fields["vision_class"] > 0.0)
            .collect();
        println!(
            "Recieved {} occupancy points. {} of them have vision class",
            points.len(),
            points_with_vision_class.len()
        );

        let rr_points = Points3D::new(
            points
                .iter()
                .map(|p| Position3D::new(p.x as f32, p.y as f32, p.z as f32)),
        )
        .with_colors(points.iter().map(|p| {
            let (r, g, b) = colorous::TURBO
                .eval_continuous(p.fields["vision_class"] / max_class as f64)
                .as_tuple();
            Color::from_rgb(r, g, b)
        }));
        let _ = rec.log("fusion/occupancy", &rr_points);
    }

    Ok(())
}
