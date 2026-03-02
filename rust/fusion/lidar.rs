// SPDX-License-Identifier: Apache-2.0
// Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

use clap::Parser;
use edgefirst_samples::Args;
use edgefirst_schemas::{decode_pcd, sensor_msgs::PointCloud2, serde_cdr::deserialize};
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

    // Create a subscriber for "rt/fusion/lidar"
    let subscriber = session.declare_subscriber("rt/fusion/lidar").await.unwrap();

    while let Ok(msg) = subscriber.recv() {
        let pcd: PointCloud2 = deserialize(&msg.payload().to_bytes())?;
        let points = decode_pcd(&pcd);
        let max_class = points
            .iter()
            .map(|x| x.fields["vision_class"] as isize)
            .max()
            .unwrap_or(1)
            .max(1);

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
        let _ = rec.log("fusion/lidar", &rr_points);
    }

    Ok(())
}
