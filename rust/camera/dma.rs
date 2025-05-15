#![cfg_attr(not(target_os = "linux"), allow(dead_code, unused_imports))]

use clap::Parser;
use edgefirst_samples::Args;
use edgefirst_schemas::edgefirst_msgs::DmaBuf;
use fourcc::FourCC;
use std::{error::Error, ffi::c_void, ptr::null_mut, slice::from_raw_parts_mut, time::Duration};
mod fourcc;
use fourcc::image_size;

#[cfg(target_os = "linux")]
#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
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

    loop {
        let dma_buf = if let Some(v) = subscriber.drain().last() {
            v
        } else {
            match subscriber.recv_timeout(Duration::from_secs(2)) {
                Ok(msg) => match msg {
                    Some(v) => v,
                    None => {
                        eprintln!(
                            "timeout receiving camera frame on {}",
                            subscriber.key_expr()
                        );
                        continue;
                    }
                },
                Err(e) => {
                    eprintln!(
                        "error receiving camera frame on {}: {:?}",
                        subscriber.key_expr(),
                        e
                    );
                    break;
                }
            }
        };
        let dma_buf: DmaBuf = cdr::deserialize(&dma_buf.payload().to_bytes()).unwrap();

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
        let fourcc: FourCC = dma_buf.fourcc.into();
        let image_size = image_size(dma_buf.width, dma_buf.height, fourcc);
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
