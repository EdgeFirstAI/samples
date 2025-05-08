use clap::Parser;
use edgefirst_schemas::edgefirst_msgs::Mask;
use rerun::{
    AnnotationContext, SegmentationImage, datatypes::ClassDescriptionMapElem, external::ndarray,
};
use std::{error::Error, path::PathBuf, time::Instant};
use zenoh::Config;
#[derive(Parser, Debug, Clone)]
struct Args {
    /// Time in seconds to run command before exiting.
    #[arg(short, long)]
    pub timeout: Option<u64>,

    /// Connect to a Zenoh router rather than peer mode.
    #[arg(short, long)]
    connect: Option<String>,

    /// Rerun file
    #[arg(short, long)]
    rerun: Option<PathBuf>,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();

    let rec = rerun::RecordingStreamBuilder::new("fusion/model_output/tracked Example").save(
        args.rerun
            .unwrap_or("fusion-model-output-tracked.rrd".into()),
    )?;

    // Create the default Zenoh configuration and if the connect argument is
    // provided set the mode to client and add the target to the endpoints.
    let mut config = Config::default();
    if let Some(connect) = args.connect {
        let post_connect = format!("['{connect}']");
        config.insert_json5("mode", "'client'").unwrap();
        config
            .insert_json5("connect/endpoints", &post_connect)
            .unwrap();
    }
    let session = zenoh::open(config).await.unwrap();

    // Create a subscriber for "rt/fusion/model_output"
    let subscriber = session
        .declare_subscriber("rt/fusion/model_output/tracked")
        .await
        .unwrap();

    let start = Instant::now();
    let _ = rec.log_static(
        "/",
        &AnnotationContext::new([
            ClassDescriptionMapElem::from((0, "Background")),
            ClassDescriptionMapElem::from((1, "Person", rerun::Rgba32::from_rgb(255, 0, 0))),
        ]),
    );
    while let Ok(msg) = subscriber.recv() {
        if let Some(timeout) = args.timeout {
            if start.elapsed().as_secs() >= timeout {
                break;
            }
        }
        let bytes = &msg.payload().to_bytes();
        let mask: Mask = cdr::deserialize(bytes)?;
        println!(
            "Recieved fusion mask output of shape {}x{}",
            mask.width, mask.height,
        );

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
