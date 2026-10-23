// SPDX-License-Identifier: Apache-2.0
// Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

use clap::Parser as _;
use edgefirst_samples::Args;
use edgefirst_schemas::sensor_msgs::Imu;
use std::error::Error;

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    // Create a subscriber for "<hostname>/imu"
    let subscriber = session
        .declare_subscriber(format!("{}/imu", args.hostname()))
        .await
        .unwrap();

    // Create Rerun logger using the provided parameters
    let (rr, _serve_guard) = args.rerun.init("imu")?;

    let rr_box =
        rerun::Boxes3D::from_half_sizes([(0.5, 0.5, 0.5)]).with_fill_mode(rerun::FillMode::Solid);
    rr.log("box", &rr_box)?;
    rr.log("box", &rerun::Transform3D::default().with_axis_length(2.0))?;

    while let Ok(msg) = subscriber.recv() {
        let imu = Imu::from_cdr(msg.payload().to_bytes())?;
        let orientation = imu.orientation();
        let x = orientation.x as f32;
        let y = orientation.y as f32;
        let z = orientation.z as f32;
        let w = orientation.w as f32;
        let pose = rerun::Quaternion([x, y, z, w]);
        rr.log("box", &rerun::Transform3D::default().with_quaternion(pose))?;
    }

    Ok(())
}
