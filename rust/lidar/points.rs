// SPDX-License-Identifier: Apache-2.0
// Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

use clap::Parser as _;
use edgefirst_samples::Args;
use edgefirst_schemas::sensor_msgs::{PointCloud2, pointcloud::DynPointCloud};
use rerun::{Points3D, Position3D};
use std::error::Error;

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    // Create a subscriber for "<hostname>/lidar/points"
    let subscriber = session
        .declare_subscriber(format!("{}/lidar/points", args.hostname()))
        .await
        .unwrap();

    // Create Rerun logger using the provided parameters
    let (rr, _serve_guard) = args.rerun.init("lidar-points")?;

    while let Ok(msg) = subscriber.recv() {
        let pcd = PointCloud2::from_cdr(msg.payload().to_bytes())?;
        let cloud = DynPointCloud::from_pointcloud2(&pcd)?;
        let points = Points3D::new(cloud.iter().map(|p| {
            Position3D::new(
                p.read_f32("x").unwrap_or(0.0),
                p.read_f32("y").unwrap_or(0.0),
                p.read_f32("z").unwrap_or(0.0),
            )
        }));
        rr.log("lidar/points", &points)?;
    }

    Ok(())
}
