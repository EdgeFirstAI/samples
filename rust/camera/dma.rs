// SPDX-License-Identifier: Apache-2.0
// Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

#![cfg_attr(not(target_os = "linux"), allow(dead_code, unused_imports))]

use clap::Parser;
use edgefirst_samples::Args;
use edgefirst_schemas::{edgefirst_msgs::DmaBuffer, serde_cdr::deserialize};
use std::{error::Error, ffi::c_void, ptr::null_mut, slice::from_raw_parts_mut};

#[cfg(target_os = "linux")]
#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    // This sample needs to run on the device, with the same permissions as the camera command.
    // We assume the camera is running with YUYV format output.

    use async_pidfd::PidFd;
    use libc::{MAP_SHARED, PROT_READ, PROT_WRITE, mmap, munmap};
    use pidfd_getfd::{GetFdFlags, get_file_from_pidfd};
    use std::os::fd::AsRawFd;

    let args = Args::parse();
    if !args.remote.is_empty() {
        eprintln!("WARNING: Camera DMA example will not work over remote connections");
    }
    let session = zenoh::open(args.clone()).await.unwrap();

    // Create Rerun logger using the provided parameters
    let (rec, _serve_guard) = args.rerun.init("camera-dma")?;

    // Create a subscriber for "rt/camera/dma"
    let subscriber = session.declare_subscriber("rt/camera/dma").await.unwrap();

    while let Ok(msg) = subscriber.recv() {
        let dma_buf: DmaBuffer = deserialize(&msg.payload().to_bytes()).unwrap();

        let pidfd: PidFd = match PidFd::from_pid(dma_buf.pid as i32) {
            Ok(v) => v,
            Err(e) => {
                eprintln!(
                    "Error getting PidFd: {:?}. Check if sample is running on same device with same permissions as camera",
                    e
                );
                break;
            }
        };

        let fd = match get_file_from_pidfd(pidfd.as_raw_fd(), dma_buf.fd, GetFdFlags::empty()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!(
                    "Error getting fd: {:?}. Check if sample is running on same device with same permissions as camera",
                    e
                );
                break;
            }
        };

        // YUYV has 2 bytes per pixel.
        let image_size = (dma_buf.width * dma_buf.height * 2) as usize;
        let mmap = unsafe {
            from_raw_parts_mut(
                mmap(
                    null_mut(),
                    image_size,
                    PROT_READ | PROT_WRITE,
                    MAP_SHARED,
                    fd.as_raw_fd(),
                    0,
                ) as *mut u8,
                image_size,
            )
        };
        let rr_image = rerun::Image::from_pixel_format(
            [dma_buf.width, dma_buf.height],
            rerun::PixelFormat::YUY2,
            mmap.to_vec(),
        );
        let _ = rec.log("camera/dma", &rr_image);

        unsafe {
            munmap(mmap.as_mut_ptr() as *mut c_void, image_size);
        }
    }

    Ok(())
}

#[cfg(not(target_os = "linux"))]
#[tokio::main]
async fn main() {
    eprintln!("Only Linux is supported for camera DMA example");
}
