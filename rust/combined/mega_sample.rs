// SPDX-License-Identifier: Apache-2.0
// Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

use std::{collections::HashSet, error::Error, sync::Arc, time::Instant};

use clap::Parser as _;
use edgefirst_samples::Args;
use edgefirst_schemas::{
    edgefirst_msgs::{Detect, Model},
    foxglove_msgs::FoxgloveCompressedVideo,
    sensor_msgs::{NavSatFix, PointCloud2, pointcloud::DynPointCloud},
};

use openh264::{decoder::Decoder, formats::YUVSource, nal_units};
use rerun::{Boxes3D, Color, Image, Points3D, Position3D};
use tokio::task;
use zenoh::{handlers::FifoChannelHandler, pubsub::Subscriber, sample::Sample};

async fn camera_h264_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>,
    rr: Arc<rerun::RecordingStream>,
) {
    let mut decoder = Decoder::new().expect("Failed to create decoder");
    let mut rgb_raw: Vec<u8> = Vec::new();

    while let Ok(msg) = sub.recv_async().await {
        let bytes = msg.payload().to_bytes();
        let video = match FoxgloveCompressedVideo::from_cdr(&bytes) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize video: {:?}", e);
                continue;
            }
        };

        for packet in nal_units(video.data()) {
            let Ok(Some(yuv)) = decoder.decode(packet) else {
                continue;
            };
            let rgb_len = yuv.rgb8_len();
            rgb_raw.resize(rgb_len, 0);
            yuv.write_rgb8(&mut rgb_raw);
            let width = yuv.dimensions().0;
            let height = yuv.dimensions().1;

            let image = Image::from_rgb24(rgb_raw.as_slice(), [width as u32, height as u32]);
            if let Err(e) = rr.log("/camera", &image) {
                eprintln!("Failed to log video: {:?}", e);
            }
        }
    }
}

async fn model_output_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>,
    rr: Arc<rerun::RecordingStream>,
) {
    let mut centers = Vec::new();
    let mut sizes = Vec::new();
    let mut labels: Vec<String> = Vec::new();

    while let Ok(msg) = sub.recv_async().await {
        let bytes = msg.payload().to_bytes();
        let model = match Model::from_cdr(&bytes) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize model output: {:?}", e);
                continue;
            }
        };

        centers.clear();
        sizes.clear();
        labels.clear();

        for b in model.masks() {
            println!(   
                "Model detected mask with size {}x{}, boxed: {}, encoding: {}",
                b.width,
                b.height,
                b.boxed,
                b.encoding
            );
            println!("Mask data length: {}", b.mask.len());
        }

        for b in model.boxes() {
            centers.push([b.center_x, b.center_y]);
            sizes.push([b.width, b.height]);
            labels.push(b.label.to_string());
            println!(
                "Model detected {} at ({}, {}) with size {}x{}",
                b.label, b.center_x, b.center_y, b.width, b.height
            );
        }

        if let Err(e) = rr.log(
            "/camera/boxes2d",
            &rerun::Boxes2D::from_centers_and_sizes(&centers, &sizes)
                .with_labels(labels.iter().map(|s| s.as_str())),
        ) {
            eprintln!("Failed to log boxes2d: {:?}", e);
            continue;
        }

        let model_time = model.model_time();
        let total_time = model_time.sec as f64 + (model_time.nanosec as f64 / 1e9);
        if let Err(e) = rr.log(
            "/metrics/detection_inference",
            &rerun::archetypes::Scalars::new([total_time]),
        ) {
            eprintln!("Failed to log detection inference: {:?}", e);
        }
    }
}

async fn radar_clusters_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>,
    rr: Arc<rerun::RecordingStream>,
) {
    let mut clustered: Vec<(f32, f32, f32, f64)> = Vec::new();

    while let Ok(msg) = sub.recv_async().await {
        let bytes = msg.payload().to_bytes();
        let pcd = match PointCloud2::from_cdr(&bytes) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize radar pointcloud: {:?}", e);
                continue;
            }
        };
        let cloud = match DynPointCloud::from_pointcloud2(&pcd) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to parse radar pointcloud: {:?}", e);
                continue;
            }
        };

        clustered.clear();
        clustered.extend(cloud.iter().filter_map(|p| {
            let id = p.read_as_f64("cluster_id").unwrap_or(0.0);
            if id > 0.0 {
                Some((
                    p.read_as_f32("x").unwrap_or(0.0),
                    p.read_as_f32("y").unwrap_or(0.0),
                    p.read_as_f32("z").unwrap_or(0.0),
                    id,
                ))
            } else {
                None
            }
        }));

        let max_cluster_id = clustered
            .iter()
            .map(|p| p.3)
            .max_by(|a, b| a.partial_cmp(b).unwrap())
            .unwrap_or(1.0)
            .max(1.0);

        let points = Points3D::new(clustered.iter().map(|p| Position3D::new(p.0, p.1, p.2)))
            .with_colors(clustered.iter().map(|p| {
                let (r, g, b) = colorous::TURBO
                    .eval_continuous(p.3 / max_cluster_id)
                    .as_tuple();
                Color::from_rgb(r, g, b)
            }));
        if let Err(e) = rr.log("/pointcloud/radar", &points) {
            eprintln!("Failed to log radar pointcloud: {:?}", e);
        }
    }
}

async fn lidar_clusters_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>,
    rr: Arc<rerun::RecordingStream>,
) {
    let mut clustered: Vec<(f32, f32, f32, f64)> = Vec::new();

    while let Ok(msg) = sub.recv_async().await {
        let bytes = msg.payload().to_bytes();
        let pcd = match PointCloud2::from_cdr(&bytes) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize lidar pointcloud: {:?}", e);
                continue;
            }
        };
        let cloud = match DynPointCloud::from_pointcloud2(&pcd) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to parse lidar pointcloud: {:?}", e);
                continue;
            }
        };

        clustered.clear();
        clustered.extend(cloud.iter().filter_map(|p| {
            let id = p.read_as_f64("cluster_id").unwrap_or(0.0);
            if id > 0.0 {
                Some((
                    p.read_as_f32("x").unwrap_or(0.0),
                    p.read_as_f32("y").unwrap_or(0.0),
                    p.read_as_f32("z").unwrap_or(0.0),
                    id,
                ))
            } else {
                None
            }
        }));

        let max_cluster_id = clustered
            .iter()
            .map(|p| p.3)
            .max_by(|a, b| a.partial_cmp(b).unwrap())
            .unwrap_or(1.0)
            .max(1.0);

        let points = Points3D::new(clustered.iter().map(|p| Position3D::new(p.0, p.1, p.2)))
            .with_colors(clustered.iter().map(|p| {
                let (r, g, b) = colorous::TURBO
                    .eval_continuous(p.3 / max_cluster_id)
                    .as_tuple();
                Color::from_rgb(r, g, b)
            }));
        if let Err(e) = rr.log("/pointcloud/lidar", &points) {
            eprintln!("Failed to log lidar pointcloud: {:?}", e);
        }
    }
}

async fn gps_handler(sub: Subscriber<FifoChannelHandler<Sample>>, rr: Arc<rerun::RecordingStream>) {
    while let Ok(msg) = sub.recv_async().await {
        let bytes = msg.payload().to_bytes();
        let gps = match NavSatFix::from_cdr(&bytes) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize GPS fix: {:?}", e);
                continue;
            }
        };
        if let Err(e) = rr.log(
            "/gps",
            &rerun::GeoPoints::from_lat_lon([(gps.latitude(), gps.longitude())]),
        ) {
            eprintln!("Failed to log GPS fix: {:?}", e);
        }
    }
}

async fn fusion_boxes3d_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>,
    rr: Arc<rerun::RecordingStream>,
) {
    while let Ok(msg) = sub.recv_async().await {
        let bytes = msg.payload().to_bytes();
        let det = match Detect::from_cdr(&bytes) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize fusion_boxes3d: {:?}", e);
                continue;
            }
        };
        let boxes = det.boxes();
        // Convert from optical frame (x=right, y=down, z=forward) to
        // standard frame (x=forward, y=left, z=up)
        let rr_boxes = Boxes3D::from_centers_and_sizes(
            boxes.iter().map(|b| (b.distance, -b.center_x, -b.center_y)),
            boxes.iter().map(|b| (b.width, b.width, b.height)),
        );
        if let Err(e) = rr.log("/pointcloud/boxes3d", &rr_boxes) {
            eprintln!("Failed to log fusion boxes3d: {:?}", e);
        }
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
        if topics.contains(topic) {
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

    subscriber.undeclare().await.unwrap();

    let (rr, _serve_guard) = args.rerun.init("mega-sample")?;
    let rr = Arc::new(rr);

    if camera_topics.contains("rt/camera/h264") {
        let sub = session.declare_subscriber("rt/camera/h264").await.unwrap();
        task::spawn(camera_h264_handler(sub, rr.clone()));
    }

    if model_topics.contains("rt/model/output") {
        let sub = session.declare_subscriber("rt/model/output").await.unwrap();
        task::spawn(model_output_handler(sub, rr.clone()));
    }

    if radar_topics.contains("rt/radar/clusters") {
        let sub = session
            .declare_subscriber("rt/radar/clusters")
            .await
            .unwrap();
        task::spawn(radar_clusters_handler(sub, rr.clone()));
    }

    if lidar_topics.contains("rt/lidar/clusters") {
        let sub = session
            .declare_subscriber("rt/lidar/clusters")
            .await
            .unwrap();
        task::spawn(lidar_clusters_handler(sub, rr.clone()));
    }

    if fusion_topics.contains("rt/fusion/boxes3d") {
        let sub = session
            .declare_subscriber("rt/fusion/boxes3d")
            .await
            .unwrap();
        task::spawn(fusion_boxes3d_handler(sub, rr.clone()));
    }

    if misc_topics.contains("rt/gps") {
        let sub = session.declare_subscriber("rt/gps").await.unwrap();
        task::spawn(gps_handler(sub, rr.clone()));
    }

    // Keep running until interrupted
    tokio::signal::ctrl_c().await?;
    Ok(())
}
