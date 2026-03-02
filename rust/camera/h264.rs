// SPDX-License-Identifier: Apache-2.0
// Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

use clap::Parser as _;
use edgefirst_samples::Args;
use edgefirst_schemas::{foxglove_msgs::FoxgloveCompressedVideo, serde_cdr::deserialize};
use openh264::decoder::Decoder;
use openh264::formats::YUVSource;
use openh264::nal_units;
use rerun::Image;
use std::error::Error;

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    // Create a subscriber for "rt/camera/h264"
    let subscriber = session.declare_subscriber("rt/camera/h264").await.unwrap();

    // Create Rerun logger using the provided parameters
    let (rr, _serve_guard) = args.rerun.init("camera-h264")?;

    let mut decoder = Decoder::new()?;

    while let Ok(msg) = subscriber.recv() {
        let video: FoxgloveCompressedVideo = deserialize(&msg.payload().to_bytes())?;
        for packet in nal_units(&video.data) {
            let Ok(Some(yuv)) = decoder.decode(packet) else {
                continue;
            };
            let rgb_len = yuv.rgb8_len();
            let mut rgb_raw = vec![0; rgb_len];
            yuv.write_rgb8(&mut rgb_raw);
            let width = yuv.dimensions().0;
            let height = yuv.dimensions().1;

            let image = Image::from_rgb24(rgb_raw, [width as u32, height as u32]);
            rr.log("image", &image)?;
        }
    }

    Ok(())
}
