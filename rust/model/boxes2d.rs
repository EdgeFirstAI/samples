// SPDX-License-Identifier: Apache-2.0
// Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

use clap::Parser as _;
use edgefirst_samples::Args;
use edgefirst_schemas::edgefirst_msgs::Model;
use std::error::Error;

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    // Create a subscriber for "rt/model/output"
    let subscriber = session.declare_subscriber("rt/model/output").await.unwrap();

    // Create Rerun logger using the provided parameters
    let (rr, _serve_guard) = args.rerun.init("model-boxes")?;

    let mut centers: Vec<[f32; 2]> = Vec::new();
    let mut sizes: Vec<[f32; 2]> = Vec::new();
    let mut labels: Vec<String> = Vec::new();

    while let Ok(msg) = subscriber.recv_async().await {
        let bytes = msg.payload().to_bytes();
        let model = Model::from_cdr(&bytes)?;

        centers.clear();
        sizes.clear();
        labels.clear();

        for b in model.boxes() {
            centers.push([b.center_x, b.center_y]);
            sizes.push([b.width, b.height]);
            labels.push(b.label.to_string());
        }

        rr.log(
            "boxes",
            &rerun::Boxes2D::from_centers_and_sizes(&centers, &sizes)
                .with_labels(labels.iter().map(|s| s.as_str())),
        )?;
    }

    Ok(())
}
