// SPDX-License-Identifier: Apache-2.0
// Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

use clap::Parser as _;
use edgefirst_samples::Args;
use edgefirst_schemas::edgefirst_msgs::Detect;
use std::error::Error;
use std::collections::HashMap;
use rand::{rng, Rng};
use rerun::{Boxes2D};

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    // Create a subscriber for "rt/model/boxes2d"
    let subscriber = session.declare_subscriber("rt/model/boxes2d").await.unwrap();

    // Create Rerun logger using the provided parameters
    let (rr, _serve_guard) = args.rerun.init("model-boxes")?;

    let mut boxes_tracked: HashMap<String, (String, [u8; 3])> = HashMap::new();

    while let Ok(msg) = subscriber.recv() {
        let detection: Detect = cdr::deserialize(&msg.payload().to_bytes())?;
        let mut centers = Vec::new();
        let mut sizes = Vec::new();
        let mut labels = Vec::new();
        let mut colors = Vec::new();

        for b in detection.boxes {
            if !b.track.id.is_empty() {
                // Insert into map if not already present
                let entry = boxes_tracked.entry(b.track.id.clone()).or_insert_with(|| {
                    let mut rng_maker = rng();
                    let random_color = [
                        rng_maker.random_range(0..=255),
                        rng_maker.random_range(0..=255),
                        rng_maker.random_range(0..=255),
                    ];
                    let short_id = &b.track.id[..6.min(b.track.id.len())];
                    let label = format!("{}: {}", b.label, short_id);
                    (label, random_color)
                });

                labels.push(entry.0.clone());
                colors.push(entry.1);
            } else {
                labels.push(b.label.clone());
                colors.push([0, 255, 0]);
            }

            centers.push([b.center_x, b.center_y]);
            sizes.push([b.width, b.height]);
        }

        let boxes = Boxes2D::from_centers_and_sizes(centers, sizes)
            .with_labels(labels)
            .with_colors(colors);

        rr.log("boxes", &boxes)?;
    }

    Ok(())
}
