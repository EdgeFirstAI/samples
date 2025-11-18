// SPDX-License-Identifier: Apache-2.0
// Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

use clap::Parser as _;
use edgefirst_samples::Args;
use edgefirst_schemas::sensor_msgs::CameraInfo;
use std::error::Error;

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    // Create a subscriber for "rt/camera/info"
    let subscriber = session.declare_subscriber("rt/camera/info").await.unwrap();

    // Create Rerun logger using the provided parameters
    let (rr, _serve_guard) = args.rerun.init("camera-info")?;

    while let Ok(msg) = subscriber.recv() {
        let info: CameraInfo = cdr::deserialize(&msg.payload().to_bytes())?;

        let width = info.width;
        let height = info.height;
        let text = "Camera Width: ".to_owned() + &width.to_string() + " Camera Height: " + &height.to_string();
        let _ = rr.log("CameraInfo", &rerun::TextLog::new(text));
    }

    Ok(())
}
