// SPDX-License-Identifier: Apache-2.0
// Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

#![cfg_attr(not(target_os = "linux"), allow(dead_code, unused_imports))]

use clap::Parser;
use edgefirst_samples::Args;
use edgefirst_schemas::edgefirst_msgs::CameraFrame;
use std::{error::Error, ffi::c_void, ptr::null_mut, slice::from_raw_parts_mut};

#[cfg(target_os = "linux")]
#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    // This sample needs to run on the device, with the same permissions as the camera command.
    // The camera service publishes NV12 frames as a stamped Tensor.

    use async_pidfd::PidFd;
    use libc::{MAP_SHARED, PROT_READ, PROT_WRITE, mmap, munmap};
    use pidfd_getfd::{GetFdFlags, get_file_from_pidfd};
    use std::os::fd::AsRawFd;

    let args = Args::parse();
    if !args.remote.is_empty() {
        eprintln!("WARNING: Camera Frame example will not work over remote connections");
    }
    let session = zenoh::open(args.clone()).await.unwrap();

    // Create Rerun logger using the provided parameters
    let (rec, _serve_guard) = args.rerun.init("camera-dma")?;

    // Create a subscriber for "<hostname>/camera/frame"
    let subscriber = session
        .declare_subscriber(format!("{}/camera/frame", args.hostname()))
        .await
        .unwrap();

    while let Ok(msg) = subscriber.recv() {
        let frame = match CameraFrame::from_cdr(msg.payload().to_bytes()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to decode CameraFrame: {:?}", e);
                continue;
            }
        };
        let tensor = frame.tensor();
        let shape: Vec<u64> = tensor.shape().collect();
        let planes: Vec<_> = tensor.planes().collect();
        let (height, width) = (shape[0] as u32, shape[1] as u32);

        let pidfd: PidFd = match PidFd::from_pid(tensor.pid() as i32) {
            Ok(v) => v,
            Err(e) => {
                eprintln!(
                    "Error getting PidFd: {:?}. Check if sample is running on same device with same permissions as camera",
                    e
                );
                break;
            }
        };

        // All planes of the frame share one DMA buffer, so the handle of the
        // first plane is enough to reach the whole frame.
        let fd = match get_file_from_pidfd(
            pidfd.as_raw_fd(),
            planes[0].handle as i32,
            GetFdFlags::empty(),
        ) {
            Ok(v) => v,
            Err(e) => {
                eprintln!(
                    "Error getting fd: {:?}. Check if sample is running on same device with same permissions as camera",
                    e
                );
                break;
            }
        };

        // Map the buffer from its start, the plane offsets are not page aligned.
        let buffer_size = planes
            .iter()
            .map(|plane| plane.offset as usize + plane.size as usize)
            .max()
            .unwrap();
        let mmap = unsafe {
            from_raw_parts_mut(
                mmap(
                    null_mut(),
                    buffer_size,
                    PROT_READ | PROT_WRITE,
                    MAP_SHARED,
                    fd.as_raw_fd(),
                    0,
                ) as *mut u8,
                buffer_size,
            )
        };
        // Copy each plane out of the mapping to assemble the complete NV12 frame.
        let nv12: Vec<u8> = planes
            .iter()
            .flat_map(|plane| {
                let start = plane.offset as usize;
                mmap[start..start + plane.used as usize].to_vec()
            })
            .collect();

        let rr_image =
            rerun::Image::from_pixel_format([width, height], rerun::PixelFormat::NV12, nv12);
        let _ = rec.log("camera/frame", &rr_image);

        unsafe {
            munmap(mmap.as_mut_ptr() as *mut c_void, buffer_size);
        }
    }

    Ok(())
}

#[cfg(not(target_os = "linux"))]
#[tokio::main]
async fn main() {
    eprintln!("Only Linux is supported for camera DMA example");
}
