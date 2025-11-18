// SPDX-License-Identifier: Apache-2.0
// Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

use clap::Parser as _;
use edgefirst_samples::Args;
use edgefirst_schemas::edgefirst_msgs::Mask;
use ndarray::{Array, Array2};
use rerun::{AnnotationContext, SegmentationImage};
use std::error::Error;
use std::io::Cursor;
use zstd::stream::decode_all;

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    // Create a subscriber for "rt/model/mask"
    let subscriber = session
        .declare_subscriber("rt/model/mask_compressed")
        .await
        .unwrap();

    // Create Rerun logger using the provided parameters
    let (rr, _serve_guard) = args.rerun.init("model-compressed_mask")?;

    while let Ok(msg) = subscriber.recv() {
        let mask: Mask = cdr::deserialize(&msg.payload().to_bytes())?;
        let decompressed_bytes = decode_all(Cursor::new(&mask.mask))?;

        let h = mask.height as usize;
        let w = mask.width as usize;
        let total_len = mask.mask.len() as u32;
        let c = (total_len / (h as u32 * w as u32)) as usize;

        let arr3 = Array::from_shape_vec([h, w, c], decompressed_bytes.clone())?;

        // Compute argmax along the last axis (class channel)
        let array2: Array2<u8> = arr3.map_axis(ndarray::Axis(2), |class_scores| {
            class_scores
                .iter()
                .enumerate()
                .max_by_key(|(_, val)| *val)
                .map(|(idx, _)| idx as u8)
                .unwrap_or(0)
        });

        // Log annotation context
        rr.log(
            "/",
            &AnnotationContext::new([
                (0, "background", rerun::Rgba32::from_rgb(0, 0, 0)),
                (1, "person", rerun::Rgba32::from_rgb(0, 255, 0)),
            ]),
        )?;

        // Log segmentation mask
        rr.log("mask", &SegmentationImage::try_from(array2)?)?;
    }

    Ok(())
}
