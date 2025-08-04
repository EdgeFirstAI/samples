use clap::Parser;
use edgefirst_samples::Args;
use edgefirst_schemas::{
    edgefirst_msgs::{Detect, DetectBox2D},
    foxglove_msgs::FoxgloveCompressedVideo,
};
use openh264::{decoder::Decoder, formats::YUVSource, nal_units};
use rerun::Image;
use std::{error::Error, sync::Arc};
use tokio::{sync::Mutex, task};
use zenoh::{handlers::FifoChannelHandler, pubsub::Subscriber, sample::Sample};

fn crop_box(mut b: DetectBox2D) -> DetectBox2D {
    if b.center_x + (b.width / 2.0) > 1.0 {
        let new_width = b.width - (b.center_x + (b.width / 2.0) - 1.0);
        b.center_x = (b.center_x - (b.width / 2.0) + 1.0) / 2.0;
        b.width = new_width;
    }
    if b.center_x - (b.width / 2.0) < 0.0 {
        let new_width = b.center_x + (b.width / 2.0);
        b.center_x = (b.center_x + (b.width / 2.0)) / 2.0;
        b.width = new_width;
    }
    if b.center_y + (b.height / 2.0) > 1.0 {
        let new_height = b.height - (b.center_y + (b.height / 2.0) - 1.0);
        b.center_y = (b.center_y - (b.height / 2.0) + 1.0) / 2.0;
        b.height = new_height;
    }
    if b.center_y - (b.height / 2.0) < 0.0 {
        let new_height = b.center_y + (b.height / 2.0);
        b.center_y = (b.center_y + (b.height / 2.0)) / 2.0;
        b.height = new_height;
    }

    b
}

async fn camera_h264_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>,
    rr: Arc<Mutex<rerun::RecordingStream>>,
    frame_size: Arc<Mutex<[u32; 2]>>,
) {
    // Create decoder inside the function
    let mut decoder = Decoder::new().expect("Failed to create decoder");

    while let Ok(msg) = sub.recv_async().await {
        let video = match cdr::deserialize::<FoxgloveCompressedVideo>(&msg.payload().to_bytes()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize video: {e:?}");
                continue;
            }
        };

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
            let rr_guard = rr.lock().await;
            if let Err(e) = rr_guard.log("/camera", &image) {
                eprintln!("Failed to log video: {e:?}");
            }

            let mut frame_size = frame_size.lock().await;
            *frame_size = [width as u32, height as u32];
        }
    }
}

async fn model_boxes2d_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>,
    rr: Arc<Mutex<rerun::RecordingStream>>,
    frame_size: Arc<Mutex<[u32; 2]>>,
) {
    while let Ok(msg) = sub.recv_async().await {
        let detection = match cdr::deserialize::<Detect>(&msg.payload().to_bytes()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize detect message: {e:?}");
                continue; // skip this message and continue
            }
        };
        let mut centers = Vec::new();
        let mut sizes = Vec::new();
        let mut labels = Vec::new();
        let size = frame_size.lock().await;
        if size[0] == 0 || size[1] == 0 {
            continue;
        }

        for b in detection.boxes {
            let b = crop_box(b);
            centers.push([b.center_x * size[0] as f32, b.center_y * size[1] as f32]);
            sizes.push([b.width * size[0] as f32, b.height * size[1] as f32]);
            labels.push(b.label);
        }
        drop(size);

        let rr_guard = rr.lock().await;
        match rr_guard.log(
            "/camera/boxes2d",
            &rerun::Boxes2D::from_centers_and_sizes(centers, sizes).with_labels(labels),
        ) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to log boxes2d: {e:?}");
                continue; // skip this message and continue
            }
        };
    }
}

// async fn model_mask_handler(
//     sub: Subscriber<FifoChannelHandler<Sample>>,
//     rr: Arc<Mutex<rerun::RecordingStream>>,
//     compressed: bool
// ) {
//     while let Ok(msg) = sub.recv_async().await {
//         let mask = match cdr::deserialize::<Mask>(&msg.payload().to_bytes()) {
//             Ok(v) => v,
//             Err(e) => {
//                 eprintln!("Failed to deserialize detect message: {:?}", e);
//                 continue; // skip this message and continue
//             }
//         };
//         let decompressed_bytes = decode_all(Cursor::new(&mask.mask))?;
//         let h = mask.height as usize;
//         let w = mask.width as usize;
//         let total_len = mask.mask.len() as u32;
//         let c = (total_len / (h as u32 * w as u32)) as usize;

//         let arr3 = Array::from_shape_vec([h, w, c], decompressed_bytes.clone())?;

//         // Compute argmax along the last axis (class channel)
//         let array2: Array2<u8> = arr3
//             .map_axis(ndarray::Axis(2), |class_scores| {
//                 class_scores
//                     .iter()
//                     .enumerate()
//                     .max_by_key(|(_, val)| *val)
//                     .map(|(idx, _)| idx as u8)
//                     .unwrap_or(0)
//             });

//         // Log segmentation mask
//         let rr_guard = rr.lock().await;
//         let _ = match rr_guard.log("/camera/mask", &SegmentationImage::try_from(array2)?) {
//             Ok(v) => v,
//             Err(e) => {
//                 eprintln!("Failed to log mask: {:?}", e);
//                 continue; // skip this message and continue
//             }
//         };
//     }
// }

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    let (rr, _serve_guard) = args.rerun.init("mega-sample")?;
    let rr = Arc::new(Mutex::new(rr));
    let frame_size = Arc::new(Mutex::new([0u32; 2]));

    let cam_sub = session.declare_subscriber("rt/camera/h264").await.unwrap();
    let cam_rr = rr.clone();
    let frame_size_cam = frame_size.clone();
    task::spawn(camera_h264_handler(cam_sub, cam_rr, frame_size_cam));

    let boxes2d_sub = session
        .declare_subscriber("rt/model/boxes2d")
        .await
        .unwrap();
    let boxes2d_rr = rr.clone();
    let frame_size_boxes2d = frame_size.clone();
    task::spawn(model_boxes2d_handler(
        boxes2d_sub,
        boxes2d_rr,
        frame_size_boxes2d,
    ));

    // if model_topics.contains("rt/model/mask_compressed") {
    //     // Log annotation context
    //     rr.lock().await.log(
    //         "/",
    //         &AnnotationContext::new([
    //             (0, "background", rerun::Rgba32::from_rgb(0, 0, 0)),
    //             (1, "person", rerun::Rgba32::from_rgb(0, 255, 0))])
    //     )?;
    //     let mask_sub = session.declare_subscriber("rt/model/mask_compressed").await.unwrap();
    //     let mask_rr = rr.clone();
    //     task::spawn(model_mask_handler(mask_sub, mask_rr, true));
    // }

    loop {}
}
