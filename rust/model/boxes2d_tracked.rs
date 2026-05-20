// SPDX-License-Identifier: Apache-2.0
// Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

use clap::Parser as _;
use edgefirst_samples::Args;
use edgefirst_schemas::edgefirst_msgs::Model;
use rand::{Rng, rng};
use rerun::Boxes2D;
use std::collections::HashMap;
use std::error::Error;

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    // Create a subscriber for "rt/model/output"
    let subscriber = session.declare_subscriber("rt/model/output").await.unwrap();

    // Create Rerun logger using the provided parameters
    let (rr, _serve_guard) = args.rerun.init("model-boxes")?;

    let mut boxes_tracked: HashMap<String, (String, [u8; 3])> = HashMap::new();
    let mut centers = Vec::new();
    let mut sizes = Vec::new();
    let mut labels = Vec::new();
    let mut colors = Vec::new();

    while let Ok(msg) = subscriber.recv_async().await {
        let bytes = msg.payload().to_bytes();
        let model = Model::from_cdr(&bytes)?;

        centers.clear();
        sizes.clear();
        labels.clear();
        colors.clear();

        for b in model.boxes() {
            if !b.track_id.is_empty() {
                let entry = boxes_tracked
                    .entry(b.track_id.to_string())
                    .or_insert_with(|| {
                        let mut rng_maker = rng();
                        let random_color = [
                            rng_maker.random_range(0..=255),
                            rng_maker.random_range(0..=255),
                            rng_maker.random_range(0..=255),
                        ];
                        let short_id = &b.track_id[..6.min(b.track_id.len())];
                        let label = format!("{}: {}", b.label, short_id);
                        (label, random_color)
                    });

                labels.push(entry.0.clone());
                colors.push(entry.1);
            } else {
                labels.push(b.label.to_string());
                colors.push([0, 255, 0]);
            }

            centers.push([b.center_x, b.center_y]);
            sizes.push([b.width, b.height]);
        }

        let boxes = Boxes2D::from_centers_and_sizes(&centers, &sizes)
            .with_labels(labels.iter().map(|s| s.as_str()))
            .with_colors(colors.iter().copied());

        rr.log("boxes", &boxes)?;
    }

    Ok(())
}
