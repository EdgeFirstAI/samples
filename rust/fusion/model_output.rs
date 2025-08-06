use clap::Parser;
use edgefirst_samples::Args;
use edgefirst_schemas::edgefirst_msgs::Mask;
use rerun::{
    AnnotationContext, SegmentationImage, datatypes::ClassDescriptionMapElem, external::ndarray,
};
use std::{error::Error, sync::Arc};
use tokio::{sync::Mutex, task};
use zenoh::{handlers::FifoChannelHandler, pubsub::Subscriber, sample::Sample};

// Finds the argmax of the slice. Panics if the slice is empty
use itertools::Itertools;
pub fn argmax_slice<T: Ord>(slice: &[T]) -> u8 {
    slice.iter().position_max().unwrap() as u8
}

async fn fusion_model_output_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>,
    rr: Arc<Mutex<rerun::RecordingStream>>,
) {
    while let Ok(msg) = sub.recv_async().await {
        let mask = match cdr::deserialize::<Mask>(&msg.payload().to_bytes()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize fusion model_output: {e:?}");
                continue; // skip this message and continue
            }
        };

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

        let rr_guard = rr.lock().await;
        match rr_guard.log("fusion/model_output", &rr_seg_image) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to log fusion model_output: {e:?}");
                continue; // skip this message and continue
            }
        };
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    let (rr, _serve_guard) = args.rerun.init("fusion-model_output")?;
    let _ = rr.log_static(
        "/",
        &AnnotationContext::new([
            ClassDescriptionMapElem::from((0, "Background")),
            ClassDescriptionMapElem::from((1, "Person", rerun::Rgba32::from_rgb(255, 0, 0))),
        ]),
    );
    let rr = Arc::new(Mutex::new(rr));

    let sub = session
        .declare_subscriber("rt/fusion/model_output")
        .await
        .unwrap();
    let rr_clone = rr.clone();
    task::spawn(fusion_model_output_handler(sub, rr_clone));

    // Rerun setup
    loop {}
}
