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

    // Create a subscriber for "rt/lidar/depth"
    let subscriber = session.declare_subscriber("rt/lidar/depth").await.unwrap();

    // Create Rerun logger using the provided parameters
    let (rr, _serve_guard) = args.rerun.init("lidar-depth")?;

    while let Ok(msg) = subscriber.recv() {
        let depth: Image = cdr::deserialize(&msg.payload().to_bytes())?;

        // Process depth image
        assert_eq!(depth.encoding, "mono16");
        let u16_from_bytes = if depth.is_bigendian > 0 {
            u16::from_be_bytes
        } else {
            u16::from_le_bytes
        };
        let pixels: Vec<u16> = depth
            .data
            .chunks_exact(2)
            .map(|a| u16_from_bytes([a[0], a[1]]))
            .collect();
        let img: Vec<_> = pixels.iter().map(|f| (f / 256) as u8).collect();
        let img = rerun::Image::from_l8(img, [depth.width, depth.height]);
        rr.log("lidar/depth", &img)?;
    }

    Ok(())
}
