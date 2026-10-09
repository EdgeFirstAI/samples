// SPDX-License-Identifier: Apache-2.0
// Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

use clap::Parser;
use edgefirst_samples::Args;
use edgefirst_schemas::sensor_msgs::{PointCloud2, pointcloud::DynPointCloud};
use rerun::{Color, Points3D, Position3D};
use std::error::Error;

///    This demo requires lidar output to be enabled on `fusion` to work.
///    By default the rt/fusion/lidar output is not enabled for `fusion`.
///    To enable it, configure LIDAR_OUTPUT_TOPIC="rt/fusion/lidar" or set
///    command line argument --lidar-output-topic=rt/fusion/lidar
#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    // Create Rerun logger using the provided parameters
    let (rec, _serve_guard) = args.rerun.init("fusion-lidar")?;

    // Create a subscriber for "<hostname>/fusion/lidar"
    let subscriber = session
        .declare_subscriber(format!("{}/fusion/lidar", args.hostname()))
        .await
        .unwrap();

    while let Ok(msg) = subscriber.recv() {
        let pcd = PointCloud2::from_cdr(msg.payload().to_bytes())?;
        let cloud = DynPointCloud::from_pointcloud2(&pcd)?;
        let points: Vec<_> = cloud.iter().collect();
        let max_class = points
            .iter()
            .map(|p| p.read_as_f64("vision_class").unwrap_or(0.0))
            .fold(1.0_f64, f64::max);

        let rr_points = Points3D::new(points.iter().map(|p| {
            Position3D::new(
                p.read_f32("x").unwrap_or(0.0),
                p.read_f32("y").unwrap_or(0.0),
                p.read_f32("z").unwrap_or(0.0),
            )
        }))
        .with_colors(points.iter().map(|p| {
            let vision_class = p.read_as_f64("vision_class").unwrap_or(0.0);
            let (r, g, b) = colorous::TURBO
                .eval_continuous(vision_class / max_class)
                .as_tuple();
            Color::from_rgb(r, g, b)
        }));
        let _ = rec.log("fusion/lidar", &rr_points);
    }

    Ok(())
}
