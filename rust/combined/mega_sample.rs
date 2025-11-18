// SPDX-License-Identifier: Apache-2.0
// Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

// use std::collections::HashSet;
// use std::time::{Duration, Instant};
// use tokio::time::sleep;
// use zenoh::handlers::FifoChannelHandler;
// use zenoh::pubsub::Subscriber;
// use std::sync::{Arc};
// use tokio::sync::Mutex;
// use clap::Parser;
// use edgefirst_samples::Args;
// use edgefirst_schemas::edgefirst_msgs::Detect;
// use rerun::Boxes3D;
// use std::error::Error;
// use clap::Parser as _;
// use edgefirst_schemas::foxglove_msgs::FoxgloveCompressedVideo;
// use rerun::{Image};
// use openh264::decoder::Decoder;
// use openh264::nal_units;
// use openh264::formats::YUVSource;
// use tokio::task;
// use edgefirst_schemas::{decode_pcd, sensor_msgs::PointCloud2};
// use rerun::{Color, Points3D, Position3D};
// use edgefirst_schemas::edgefirst_msgs::Mask;
// use ndarray::{Array2, Array};
// use zstd::stream::decode_all;
// use std::io::Cursor;
// use rerun::{AnnotationContext, SegmentationImage};
// use edgefirst_schemas::sensor_msgs::NavSatFix;
// use zenoh::sample::Sample;

use std::{collections::HashSet, error::Error, sync::Arc, time::Instant};

use clap::Parser;
use edgefirst_samples::Args;
use edgefirst_schemas::{
    decode_pcd,
    edgefirst_msgs::Detect,
    foxglove_msgs::FoxgloveCompressedVideo,
    sensor_msgs::{NavSatFix, PointCloud2},
};

use openh264::{decoder::Decoder, formats::YUVSource, nal_units};
use rerun::{Boxes3D, Color, Image, Points3D, Position3D};
use tokio::{sync::Mutex, task};
use zenoh::{handlers::FifoChannelHandler, pubsub::Subscriber, sample::Sample};

async fn camera_h264_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>,
    rr: Arc<Mutex<rerun::RecordingStream>>,
) {
    // Create decoder inside the function
    let mut decoder = Decoder::new().expect("Failed to create decoder");

    while let Ok(msg) = sub.recv_async().await {
        let video = match cdr::deserialize::<FoxgloveCompressedVideo>(&msg.payload().to_bytes()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize video: {:?}", e);
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
                eprintln!("Failed to log video: {:?}", e);
            }
        }
    }
}

async fn model_boxes2d_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>,
    rr: Arc<Mutex<rerun::RecordingStream>>,
) {
    while let Ok(msg) = sub.recv_async().await {
        let detection = match cdr::deserialize::<Detect>(&msg.payload().to_bytes()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize detect message: {:?}", e);
                continue; // skip this message and continue
            }
        };
        let mut centers = Vec::new();
        let mut sizes = Vec::new();
        let mut labels = Vec::new();

        for b in detection.boxes {
            centers.push([b.center_x * 960.0, b.center_y * 540.0]);
            sizes.push([b.width * 960.0, b.height * 540.0]);
            labels.push(b.label);
        }

        let rr_guard = rr.lock().await;
        match rr_guard.log(
            "/camera/boxes2d",
            &rerun::Boxes2D::from_centers_and_sizes(centers, sizes).with_labels(labels),
        ) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to log boxes2d: {:?}", e);
                continue; // skip this message and continue
            }
        };
        let model_time_sec = detection.model_time.sec as f64;
        let model_time_nsec = detection.model_time.nanosec as f64;
        let total_time = model_time_sec + (model_time_nsec / 1e9);
        match rr_guard.log(
            "/metrics/detection_inference",
            &rerun::archetypes::Scalars::new([total_time]),
        ) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to log detection inference: {:?}", e);
                continue; // skip this message and continue
            }
        };
    }
}

// async fn model_mask_handler(
//     sub: Subscriber<FifoChannelHandler<Sample>>,
//     rr: Arc<Mutex<rerun::RecordingStream>>,
//     compressed: Bool
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

async fn radar_clusters_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>,
    rr: Arc<Mutex<rerun::RecordingStream>>,
) {
    while let Ok(msg) = sub.recv_async().await {
        let pcd = match cdr::deserialize::<PointCloud2>(&msg.payload().to_bytes()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize radar pointcloud: {:?}", e);
                continue; // skip this message and continue
            }
        };
        let points = decode_pcd(&pcd);
        let clustered_points: Vec<_> = points.iter().filter(|x| x.id > 0).collect();
        let max_cluster_id = clustered_points
            .iter()
            .map(|x| x.id)
            .max()
            .unwrap_or(1)
            .max(1);

        let points = Points3D::new(
            clustered_points
                .iter()
                .map(|p| Position3D::new(p.x as f32, p.y as f32, p.z as f32)),
        )
        .with_colors(clustered_points.iter().map(|p| {
            let (r, g, b) = colorous::TURBO
                .eval_continuous(p.id as f64 / max_cluster_id as f64)
                .as_tuple();
            Color::from_rgb(r, g, b)
        }));
        let rr_guard = rr.lock().await;
        match rr_guard.log("/pointcloud/radar", &points) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to log radar pointcloud: {:?}", e);
                continue; // skip this message and continue
            }
        };
    }
}

async fn lidar_clusters_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>,
    rr: Arc<Mutex<rerun::RecordingStream>>,
) {
    while let Ok(msg) = sub.recv_async().await {
        let pcd = match cdr::deserialize::<PointCloud2>(&msg.payload().to_bytes()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize radar pointcloud: {:?}", e);
                continue; // skip this message and continue
            }
        };
        let points = decode_pcd(&pcd);
        let clustered_points: Vec<_> = points.iter().filter(|x| x.id > 0).collect();
        let max_cluster_id = clustered_points
            .iter()
            .map(|x| x.id)
            .max()
            .unwrap_or(1)
            .max(1);

        let points = Points3D::new(
            clustered_points
                .iter()
                .map(|p| Position3D::new(p.x as f32, p.y as f32, p.z as f32)),
        )
        .with_colors(clustered_points.iter().map(|p| {
            let (r, g, b) = colorous::TURBO
                .eval_continuous(p.id as f64 / max_cluster_id as f64)
                .as_tuple();
            Color::from_rgb(r, g, b)
        }));
        let rr_guard = rr.lock().await;
        match rr_guard.log("/pointcloud/lidar", &points) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to log radar pointcloud: {:?}", e);
                continue; // skip this message and continue
            }
        };
    }
}

async fn gps_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>,
    rr: Arc<Mutex<rerun::RecordingStream>>,
) {
    while let Ok(msg) = sub.recv_async().await {
        let gps = match cdr::deserialize::<NavSatFix>(&msg.payload().to_bytes()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize radar pointcloud: {:?}", e);
                continue; // skip this message and continue
            }
        };
        let rr_guard = rr.lock().await;
        match rr_guard.log(
            "/gps",
            &rerun::GeoPoints::from_lat_lon([(gps.latitude, gps.longitude)]),
        ) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to log radar pointcloud: {:?}", e);
                continue; // skip this message and continue
            }
        };
    }
}

async fn fusion_boxes3d_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>,
    rr: Arc<Mutex<rerun::RecordingStream>>,
) {
    while let Ok(msg) = sub.recv_async().await {
        let det = match cdr::deserialize::<Detect>(&msg.payload().to_bytes()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize fusion_boxes3d: {:?}", e);
                continue; // skip this message and continue
            }
        };
        let boxes = det.boxes;
        // The 3D boxes are in an _optical frame of reference, where x is right, y is down, and z (distance) is forward
        // We will convert them to a normal frame of reference, where x is forward, y is left, and z is up
        let rr_boxes = Boxes3D::from_centers_and_sizes(
            boxes.iter().map(|b| (b.distance, -b.center_x, -b.center_y)),
            boxes.iter().map(|b| (b.width, b.width, b.height)),
        );
        let rr_guard = rr.lock().await;
        match rr_guard.log("/pointcloud/boxes3d", &rr_boxes) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to log fusion boxes3d: {:?}", e);
                continue; // skip this message and continue
            }
        };
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    // Create a subscriber for all topics matching the pattern "rt/**"
    let subscriber = session.declare_subscriber("rt/**").await.unwrap();

    // Sets for discovered topics
    let mut topics = HashSet::new();
    let mut camera_topics = HashSet::new();
    let mut model_topics = HashSet::new();
    let mut radar_topics = HashSet::new();
    let mut fusion_topics = HashSet::new();
    let mut lidar_topics = HashSet::new();
    let mut misc_topics = HashSet::new();

    let start = Instant::now();

    println!("Gathering available topics");
    while let Ok(msg) = subscriber.recv() {
        if start.elapsed().as_secs() >= 5 {
            break;
        }
        let topic = msg.key_expr().as_str();
        // Ignore message if the topic is known otherwise save the topic
        if topics.contains(msg.key_expr().as_str()) {
            continue;
        }
        topics.insert(msg.key_expr().to_string());

        if topic.contains("rt/camera") {
            camera_topics.insert(msg.key_expr().to_string());
        } else if topic.contains("rt/model") {
            model_topics.insert(msg.key_expr().to_string());
        } else if topic.contains("rt/radar") {
            radar_topics.insert(msg.key_expr().to_string());
        } else if topic.contains("rt/fusion") {
            fusion_topics.insert(msg.key_expr().to_string());
        } else if topic.contains("rt/lidar") {
            lidar_topics.insert(msg.key_expr().to_string());
        } else {
            misc_topics.insert(msg.key_expr().to_string());
        }
    }

    // Undeclare subscriber
    subscriber.undeclare().await.unwrap();

    let (rr, _serve_guard) = args.rerun.init("mega-sample")?;
    let rr = Arc::new(Mutex::new(rr));

    if camera_topics.contains("rt/camera/h264") {
        let cam_sub = session.declare_subscriber("rt/camera/h264").await.unwrap();
        let cam_rr = rr.clone();
        task::spawn(camera_h264_handler(cam_sub, cam_rr));
    }

    if model_topics.contains("rt/model/boxes2d") {
        let boxes2d_sub = session
            .declare_subscriber("rt/model/boxes2d")
            .await
            .unwrap();
        let boxes2d_rr = rr.clone();
        task::spawn(model_boxes2d_handler(boxes2d_sub, boxes2d_rr));
    }

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

    if radar_topics.contains("rt/radar/clusters") {
        let radar_sub = session
            .declare_subscriber("rt/radar/clusters")
            .await
            .unwrap();
        let radar_rr = rr.clone();
        task::spawn(radar_clusters_handler(radar_sub, radar_rr));
    }

    if lidar_topics.contains("rt/lidar/clusters") {
        let lidar_sub = session
            .declare_subscriber("rt/lidar/clusters")
            .await
            .unwrap();
        let lidar_rr = rr.clone();
        task::spawn(lidar_clusters_handler(lidar_sub, lidar_rr));
    }

    if fusion_topics.contains("rt/fusion/boxes3d") {
        let boxes3d_sub = session
            .declare_subscriber("rt/fusion/boxes3d")
            .await
            .unwrap();
        let boxes3d_rr = rr.clone();
        task::spawn(fusion_boxes3d_handler(boxes3d_sub, boxes3d_rr));
    }

    if misc_topics.contains("rt/gps") {
        let gps_sub = session.declare_subscriber("rt/gps").await.unwrap();
        let gps_rr = rr.clone();
        task::spawn(gps_handler(gps_sub, gps_rr));
    }

    // Rerun setup
    loop {}
    Ok(())
}
