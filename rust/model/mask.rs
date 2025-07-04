use clap::Parser as _;
use edgefirst_samples::Args;
use edgefirst_schemas::edgefirst_msgs::Mask;
use ndarray::{Array2, Array};
use rerun::{AnnotationContext, SegmentationImage};
use std::{error::Error, sync::Arc};
use tokio::{sync::Mutex, task};
use zenoh::{handlers::FifoChannelHandler, pubsub::Subscriber, sample::Sample};

async fn model_mask_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>,
    rr: Arc<Mutex<rerun::RecordingStream>>,
) {
    while let Ok(msg) = sub.recv_async().await {
        let mask = match cdr::deserialize::<Mask>(&msg.payload().to_bytes()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize model info: {:?}", e);
                continue; // skip this message and continue
            }
        };

        let h = mask.height as usize;
        let w = mask.width as usize;
        let total_len = mask.mask.len() as u32;
        let c = (total_len / (h as u32 * w as u32)) as usize;

        let arr3 = match Array::from_shape_vec((h, w, c), mask.mask.clone()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to form the mask array: {:?}", e);
                continue;
            }
        };
        
        // Compute argmax along the last axis (class channel)
        let array2: Array2<u8> = arr3
            .map_axis(ndarray::Axis(2), |class_scores| {
                class_scores
                    .iter()
                    .enumerate()
                    .max_by_key(|(_, val)| *val)
                    .map(|(idx, _)| idx as u8)
                    .unwrap_or(0)
            });

        let seg_img = match SegmentationImage::try_from(array2) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to convert to SegmentationImage: {:?}", e);
                continue;
            }
        };

        // Log segmentation mask
        let rr_guard = rr.lock().await;
        let _ = match rr_guard.log("model/mask", &seg_img) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to log mask: {:?}", e);
                continue; // skip this message and continue
            }
        };
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    let (rr, _serve_guard) = args.rerun.init("model-mask")?;

    // Log annotation context
    rr.log(
        "/",
        &AnnotationContext::new([
            (0, "background", rerun::Rgba32::from_rgb(0, 0, 0)),
            (1, "person", rerun::Rgba32::from_rgb(0, 255, 0))])
    )?;

    let rr = Arc::new(Mutex::new(rr));

    let sub = session.declare_subscriber("rt/model/mask").await.unwrap();
    let rr_clone = rr.clone();
    task::spawn(model_mask_handler(sub, rr_clone));

    // Rerun setup
    loop {
        
    }
}
