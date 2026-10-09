// SPDX-License-Identifier: Apache-2.0
// Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

// "model/output" (edgefirst_msgs/Model) is the default model topic on
// EdgeFirst Perception 2.8+, combining detection boxes and segmentation
// masks in one message. See boxes2d.rs, boxes2d_tracked.rs, mask.rs and
// compressed_mask.rs for the legacy topics' opt-in steps.

use clap::Parser as _;
use edgefirst_samples::Args;
use edgefirst_schemas::edgefirst_msgs::Model;
use ndarray::{Array, Array2};
use rerun::{AnnotationContext, Boxes2D, SegmentationImage};
use std::error::Error;

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    // Create a subscriber for "<hostname>/model/output"
    let subscriber = session
        .declare_subscriber(format!("{}/model/output", args.hostname()))
        .await
        .unwrap();

    // Create Rerun logger using the provided parameters
    let (rr, _serve_guard) = args.rerun.init("model-output")?;

    while let Ok(msg) = subscriber.recv() {
        let model = Model::from_cdr(msg.payload().to_bytes())?;

        let mut centers = Vec::new();
        let mut sizes = Vec::new();
        let mut labels = Vec::new();
        for b in model.boxes() {
            centers.push([b.center_x, b.center_y]);
            sizes.push([b.width, b.height]);
            labels.push(b.label);
        }
        rr.log(
            "boxes",
            &Boxes2D::from_centers_and_sizes(centers, sizes).with_labels(labels),
        )?;

        for mask in model.masks() {
            let h = mask.height as usize;
            let w = mask.width as usize;
            let c = mask.mask.len() / (h * w);

            let arr3 = Array::from_shape_vec((h, w, c), mask.mask.to_vec())?;
            let array2: Array2<u8> = arr3.map_axis(ndarray::Axis(2), |class_scores| {
                class_scores
                    .iter()
                    .enumerate()
                    .max_by_key(|(_, val)| *val)
                    .map(|(idx, _)| idx as u8)
                    .unwrap_or(0)
            });

            rr.log(
                "/",
                &AnnotationContext::new([
                    (0, "background", rerun::Rgba32::from_rgb(0, 0, 0)),
                    (1, "person", rerun::Rgba32::from_rgb(0, 255, 0)),
                ]),
            )?;
            rr.log("mask", &SegmentationImage::try_from(array2)?)?;
        }
    }

    Ok(())
}
