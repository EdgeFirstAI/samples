// SPDX-License-Identifier: Apache-2.0
// Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

use clap::Parser as _;
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
    let (rr, _serve_guard) = args.rerun.init("fusion-lidar")?;

    // Create a subscriber for "rt/fusion/lidar"
    let subscriber = session.declare_subscriber("rt/fusion/lidar").await.unwrap();

    let mut points: Vec<(f32, f32, f32, f64)> = Vec::new();

    while let Ok(msg) = subscriber.recv_async().await {
        let bytes = msg.payload().to_bytes();
        let pcd = PointCloud2::from_cdr(&bytes)?;
        let cloud = DynPointCloud::from_pointcloud2(&pcd)?;

        // Collect points with vision_class for multi-pass iteration
        points.clear();
        points.extend(cloud.iter().map(|p| {
            (
                p.read_as_f32("x").unwrap_or(0.0),
                p.read_as_f32("y").unwrap_or(0.0),
                p.read_as_f32("z").unwrap_or(0.0),
                p.read_as_f64("vision_class").unwrap_or(0.0),
            )
        }));

        let max_class = points
            .iter()
            .map(|p| p.3 as isize)
            .max()
            .unwrap_or(1)
            .max(1);

        let rr_points = Points3D::new(points.iter().map(|p| Position3D::new(p.0, p.1, p.2)))
            .with_colors(points.iter().map(|p| {
                let (r, g, b) = colorous::TURBO
                    .eval_continuous(p.3 / max_class as f64)
                    .as_tuple();
                Color::from_rgb(r, g, b)
            }));
        rr.log("fusion/lidar", &rr_points)?;
    }

    Ok(())
}
