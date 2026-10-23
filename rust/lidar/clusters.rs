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

    // Create a subscriber for "<hostname>/lidar/clusters"
    let subscriber = session
        .declare_subscriber(format!("{}/lidar/clusters", args.hostname()))
        .await
        .unwrap();

    // Create Rerun logger using the provided parameters
    let (rr, _serve_guard) = args.rerun.init("lidar-clusters")?;

    while let Ok(msg) = subscriber.recv() {
        let pcd = PointCloud2::from_cdr(msg.payload().to_bytes())?;
        let cloud = DynPointCloud::from_pointcloud2(&pcd)?;
        let clustered_points: Vec<_> = cloud
            .iter()
            .filter(|p| p.read_as_f64("cluster_id").unwrap_or(0.0) > 0.0)
            .collect();
        let max_cluster_id = clustered_points
            .iter()
            .map(|p| p.read_as_f64("cluster_id").unwrap_or(0.0))
            .fold(1.0_f64, f64::max);

        let points = Points3D::new(clustered_points.iter().map(|p| {
            Position3D::new(
                p.read_f32("x").unwrap_or(0.0),
                p.read_f32("y").unwrap_or(0.0),
                p.read_f32("z").unwrap_or(0.0),
            )
        }))
        .with_colors(clustered_points.iter().map(|p| {
            let cluster_id = p.read_as_f64("cluster_id").unwrap_or(0.0);
            let (r, g, b) = colorous::TURBO
                .eval_continuous(cluster_id / max_cluster_id)
                .as_tuple();
            Color::from_rgb(r, g, b)
        }));
        rr.log("lidar/clusters", &points)?;
    }

    Ok(())
}
