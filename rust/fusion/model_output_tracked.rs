// SPDX-License-Identifier: Apache-2.0
// Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

use clap::Parser;
use edgefirst_samples::Args;
use edgefirst_schemas::{edgefirst_msgs::Mask, serde_cdr::deserialize};
use rerun::{
    AnnotationContext, SegmentationImage, datatypes::ClassDescriptionMapElem, external::ndarray,
};
use std::error::Error;

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    // Create Rerun logger using the provided parameters
    let (rec, _serve_guard) = args.rerun.init("fusion-model_output-tracked")?;

    // Create a subscriber for "rt/fusion/model_output"
    let subscriber = session
        .declare_subscriber("rt/fusion/model_output/tracked")
        .await
        .unwrap();

    let _ = rec.log_static(
        "/",
        &AnnotationContext::new([
            ClassDescriptionMapElem::from((0, "Background")),
            ClassDescriptionMapElem::from((1, "Person", rerun::Rgba32::from_rgb(255, 0, 0))),
        ]),
    );
    while let Ok(msg) = subscriber.recv() {
        let bytes = &msg.payload().to_bytes();
        let mask: Mask = deserialize(bytes)?;

        let mask_classes = mask.mask.len() / mask.width as usize / mask.height as usize;
        let mask_argmax: Vec<u8> = mask
            .mask
            .chunks_exact(mask_classes)
            .map(argmax_slice)
            .collect();
        let mask = ndarray::Array2::from_shape_vec(
            [mask.width as usize, mask.height as usize],
            mask_argmax,
        )
        .unwrap();
        let rr_seg_image = SegmentationImage::try_from(mask).unwrap();
        let _ = rec.log("fusion/model_output/tracked", &rr_seg_image);
    }

    Ok(())
}

// Finds the argmax of the slice. Panics if the slice is empty
use itertools::Itertools;
pub fn argmax_slice<T: Ord>(slice: &[T]) -> u8 {
    slice.iter().position_max().unwrap() as u8
}
