// SPDX-License-Identifier: Apache-2.0
// Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

use clap::Parser as _;
use edgefirst_samples::Args;
use edgefirst_schemas::foxglove_msgs::FoxgloveCompressedVideo;
use edgefirst::image::{TensorImage, ImageConverter, RGB};
use edgefirst::image::ImageConverterTrait;
use edgefirst::tensor::{Tensor, TensorMemory, TensorMapTrait, TensorTrait};
use edgefirst::tensor::Error as TensorError;
use edgefirst::image::{Rotation, Flip, Crop};
use edgefirst::decoder::Decoder as EFDecoder;
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
        let video: FoxgloveCompressedVideo = cdr::deserialize(&msg.payload().to_bytes())?;
        for packet in nal_units(&video.data) {
            let Ok(Some(yuv)) = decoder.decode(packet) else {
                continue;
            };
            let rgb_len = yuv.rgb8_len();
            let mut rgb_raw = vec![0; rgb_len];
            yuv.write_rgb8(&mut rgb_raw);
            let width = yuv.dimensions().0;
            let height = yuv.dimensions().1;

            // let image = Image::from_rgb24(rgb_raw.clone(), [width as u32, height as u32]);
            // rr.log("image", &image)?;

            let tensor = Tensor::<u8>::new(&[width as usize, height as usize, 3], Some(TensorMemory::Mem), Some("test_tensor"))
                .map_err(|e| format!("Failed to create Tensor: {:?}", e))?;
            
            let mut map = tensor.map().map_err(|e| format!("Failed to map Tensor memory: {:?}", e))?;

            map.copy_from_slice(&rgb_raw);
            
            drop(map); // Unmap the tensor memory
            let tensor_image = TensorImage::from_tensor(tensor, RGB)
                .map_err(|e| format!("Failed to create TensorImage: {:?}", e))?;
            // println!("Created TensorImage of size {}x{}", tensor_image.width(), tensor_image.height());
            let mut converter = ImageConverter::new()
                .map_err(|e| format!("Failed to create ImageConverter: {:?}", e))?;
            let mut dst = TensorImage::new(1920, 1080, RGB, None)
                .map_err(|e| format!("Failed to create destination TensorImage: {:?}", e))?;
            converter.convert(&tensor_image, &mut dst, Rotation::Rotate180, Flip::None, Crop::default())
                .map_err(|e| format!("Failed to convert image: {:?}", e))?;

            // // let _ = dst.save_jpeg("test.jpeg", 90);

            let dst_map = dst.tensor().map().map_err(|e| format!("Failed to map destination Tensor memory: {:?}", e))?;

            let im = Image::from_rgb24(dst_map.to_vec(), [width as u32, height as u32]);
            rr.log("image", &im)?;
            drop(dst_map); // Unmap the destination tensor memory
        }
    }

    Ok(())
}
