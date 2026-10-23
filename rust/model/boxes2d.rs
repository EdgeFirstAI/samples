// SPDX-License-Identifier: Apache-2.0
// Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

// NOTE: "model/boxes2d" is disabled by default on EdgeFirst Perception 2.8+.
// Enable it by setting DETECT_TOPIC=model/boxes2d in /etc/default/model on
// the device, or use the "model-output" (Model) sample instead.

use clap::Parser as _;
use edgefirst_samples::Args;
use edgefirst_schemas::edgefirst_msgs::Detect;
use std::error::Error;

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    // Create a subscriber for "<hostname>/model/boxes2d"
    let subscriber = session
        .declare_subscriber(format!("{}/model/boxes2d", args.hostname()))
        .await
        .unwrap();

    // Create Rerun logger using the provided parameters
    let (rr, _serve_guard) = args.rerun.init("model-boxes")?;

    while let Ok(msg) = subscriber.recv() {
        let detection = Detect::from_cdr(msg.payload().to_bytes())?;

        let mut centers = Vec::new();
        let mut sizes = Vec::new();
        let mut labels = Vec::new();

        for b in detection.boxes() {
            centers.push([b.center_x, b.center_y]);
            sizes.push([b.width, b.height]);
            labels.push(b.label);
        }

        rr.log(
            "boxes",
            &rerun::Boxes2D::from_centers_and_sizes(centers, sizes).with_labels(labels),
        )?;
    }

    Ok(())
}
