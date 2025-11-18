// SPDX-License-Identifier: Apache-2.0
// Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

use clap::Parser as _;
use edgefirst_samples::Args;
use edgefirst_schemas::sensor_msgs::Image;
use std::error::Error;

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    // Create a subscriber for "rt/lidar/reflect"
    let subscriber = session
        .declare_subscriber("rt/lidar/reflect")
        .await
        .unwrap();

    // Create Rerun logger using the provided parameters
    let (rr, _serve_guard) = args.rerun.init("lidar-depth")?;

    while let Ok(msg) = subscriber.recv() {
        let reflect: Image = cdr::deserialize(&msg.payload().to_bytes())?;

        // Reflectivity image must be mono8
        assert_eq!(reflect.encoding, "mono8");

        let img = rerun::Image::from_l8(reflect.data, [reflect.width, reflect.height]);
        rr.log("lidar/reflect", &img)?;
    }

    Ok(())
}
