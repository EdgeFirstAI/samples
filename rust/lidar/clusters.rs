// SPDX-License-Identifier: Apache-2.0
// Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

use clap::Parser as _;
use edgefirst_samples::Args;
use edgefirst_schemas::sensor_msgs::{PointCloud2, pointcloud::DynPointCloud};
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

    let mut clustered: Vec<(f32, f32, f32, f64)> = Vec::new();

    while let Ok(msg) = subscriber.recv_async().await {
        let bytes = msg.payload().to_bytes();
        let pcd = PointCloud2::from_cdr(&bytes)?;
        let cloud = DynPointCloud::from_pointcloud2(&pcd)?;

        // Collect clustered points (cluster_id > 0) for multi-pass iteration
        clustered.clear();
        clustered.extend(cloud.iter().filter_map(|p| {
            let id = p.read_as_f64("cluster_id").unwrap_or(0.0);
            if id > 0.0 {
                Some((
                    p.read_as_f32("x").unwrap_or(0.0),
                    p.read_as_f32("y").unwrap_or(0.0),
                    p.read_as_f32("z").unwrap_or(0.0),
                    id,
                ))
            } else {
                None
            }
        }));

        let max_cluster_id = clustered
            .iter()
            .map(|p| p.3)
            .max_by(|a, b| a.partial_cmp(b).unwrap())
            .unwrap_or(1.0)
            .max(1.0);

        let points = Points3D::new(clustered.iter().map(|p| Position3D::new(p.0, p.1, p.2)))
            .with_colors(clustered.iter().map(|p| {
                let (r, g, b) = colorous::TURBO
                    .eval_continuous(p.3 / max_cluster_id)
                    .as_tuple();
                Color::from_rgb(r, g, b)
            }));
        rr.log("lidar/clusters", &points)?;
    }

    Ok(())
}
