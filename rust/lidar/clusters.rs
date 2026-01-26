// SPDX-License-Identifier: Apache-2.0
// Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

use clap::Parser as _;
use edgefirst_samples::Args;
use edgefirst_schemas::{decode_pcd, sensor_msgs::PointCloud2, serde_cdr::deserialize};
use rerun::{Color, Points3D, Position3D};
use std::error::Error;

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    // Create a subscriber for "rt/lidar/clusters"
    let subscriber = session
        .declare_subscriber("rt/lidar/clusters")
        .await
        .unwrap();

    // Create Rerun logger using the provided parameters
    let (rr, _serve_guard) = args.rerun.init("lidar-clusters")?;

    while let Ok(msg) = subscriber.recv() {
        let pcd: PointCloud2 = deserialize(&msg.payload().to_bytes())?;
        let points = decode_pcd(&pcd);
        let clustered_points: Vec<_> = points.iter().filter(|x| x.id > 0).collect();
        let max_cluster_id = clustered_points
            .iter()
            .map(|x| x.id)
            .max()
            .unwrap_or(1)
            .max(1);

        let points = Points3D::new(
            clustered_points
                .iter()
                .map(|p| Position3D::new(p.x as f32, p.y as f32, p.z as f32)),
        )
        .with_colors(clustered_points.iter().map(|p| {
            let (r, g, b) = colorous::TURBO
                .eval_continuous(p.id as f64 / max_cluster_id as f64)
                .as_tuple();
            Color::from_rgb(r, g, b)
        }));
        rr.log("lidar/clusters", &points)?;
    }

    Ok(())
}
