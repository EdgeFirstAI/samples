// SPDX-License-Identifier: Apache-2.0
// Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

use clap::Parser as _;
use edgefirst_samples::Args;
use edgefirst_schemas::edgefirst_msgs::Model;
use ndarray::{Array, Array2};
use rerun::{AnnotationContext, SegmentationImage};
use std::error::Error;

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    // Create a subscriber for "rt/model/output"
    let subscriber = session.declare_subscriber("rt/model/output").await.unwrap();

    // Create Rerun logger using the provided parameters
    let (rr, _serve_guard) = args.rerun.init("model-mask")?;

    // Log annotation context once as static data
    rr.log_static(
        "/",
        &AnnotationContext::new([
            (0, "background", rerun::Rgba32::from_rgb(0, 0, 0)),
            (1, "person", rerun::Rgba32::from_rgb(0, 255, 0)),
        ]),
    )?;

    while let Ok(msg) = subscriber.recv_async().await {
        let bytes = msg.payload().to_bytes();
        let model = Model::from_cdr(&bytes)?;

        let masks = model.masks();
        let Some(mask) = masks.first() else {
            continue;
        };

        let h = mask.height as usize;
        let w = mask.width as usize;
        let c = mask.mask.len() / (h * w);

        let arr3 = Array::from_shape_vec((h, w, c), mask.mask.to_vec())?;

        // Compute argmax along the last axis (class channel)
        let array2: Array2<u8> = arr3.map_axis(ndarray::Axis(2), |class_scores| {
            class_scores
                .iter()
                .enumerate()
                .max_by_key(|(_, val)| *val)
                .map(|(idx, _)| idx as u8)
                .unwrap_or(0)
        });

        rr.log("mask", &SegmentationImage::try_from(array2)?)?;
    }

    Ok(())
}
