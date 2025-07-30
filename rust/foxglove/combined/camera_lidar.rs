use std::{
    error::Error,
    sync::Arc,
    thread,
    io::Cursor
};
use clap::Parser;
use byteorder::WriteBytesExt;
use edgefirst_samples::Args;
use edgefirst_schemas::{
    decode_pcd,
    edgefirst_msgs::{Detect, DetectBox2D},
    foxglove_msgs::FoxgloveCompressedVideo,
    sensor_msgs::{PointCloud2},
};
use foxglove::{WebSocketServer, log,
    schemas::{Timestamp, CompressedVideo, PointCloud, PackedElementField,
              Quaternion, Vector3, Pose}
};
use openh264::{decoder::Decoder, formats::YUVSource, nal_units};
use rerun::{Boxes3D, Color, Image, Points3D, Position3D};
use tokio::{sync::Mutex, task};
use zenoh::{handlers::FifoChannelHandler, pubsub::Subscriber, sample::Sample};


fn crop_box(mut b: DetectBox2D)
    -> DetectBox2D {
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

async fn camera_h264_handler(sub: Subscriber<FifoChannelHandler<Sample>>) {
    while let Ok(msg) = sub.recv_async().await {
        let video = match cdr::deserialize::<FoxgloveCompressedVideo>(&msg.payload().to_bytes()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize video: {:?}", e);
                continue;
            }
        };

        let ts = Timestamp::new(video.header.stamp.sec as u32, video.header.stamp.nanosec as u32);
        let cv = CompressedVideo {
            timestamp: Some(ts),
            frame_id: video.header.frame_id.clone(),
            data: video.data.clone().into(),
            format: video.format.clone(),
        };
        log!("/camera", cv)
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
                eprintln!("Failed to deserialize detect message: {:?}", e);
                continue; // skip this message and continue
            }
        };
        let mut centers = Vec::new();
        let mut sizes = Vec::new();
        let mut labels = Vec::new();
        let size = frame_size.lock().await;
        if size[0] == 0 || size[1] == 0 { continue; }

        for b in detection.boxes {
            let b = crop_box(b);
            centers.push([b.center_x * size[0] as f32, b.center_y * size[1] as f32]);
            sizes.push([b.width * size[0] as f32, b.height * size[1] as f32]);
            labels.push(b.label);
        }
        drop(size);

        let rr_guard = rr.lock().await;
        let _ = match rr_guard.log("/camera/boxes2d", &rerun::Boxes2D::from_centers_and_sizes(centers, sizes).with_labels(labels)) {
                Ok(v) => v,
                Err(e) => {
                    eprintln!("Failed to log boxes2d: {:?}", e);
                continue; // skip this message and continue
                }
            };   
    }
}

async fn lidar_clusters_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>
) {
    while let Ok(msg) = sub.recv_async().await {
        let pcd = match cdr::deserialize::<PointCloud2>(&msg.payload().to_bytes()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize lidar pointcloud: {:?}", e);
                continue; // skip this message and continue
            }
        };
        let clustered_points: Vec<_> = decode_pcd(&pcd).into_iter().filter(|p| p.id > 0).collect();
        let max_cluster_id = clustered_points
            .iter()
            .map(|p| p.id)
            .max()
            .unwrap_or(1)
            .max(1);

        let mut buffer = Vec::with_capacity(clustered_points.len() * 28); // 7 f32 values per point
        let mut cursor = Cursor::new(&mut buffer);

        for p in &clustered_points {
            let (r, g, b) = colorous::TURBO
                .eval_continuous(p.id as f64 / max_cluster_id as f64)
                .as_tuple();

            // Normalize u8 RGB to 0.0–1.0
            let r = r as f32 / 255.0;
            let g = g as f32 / 255.0;
            let b = b as f32 / 255.0;

            cursor.write_f32_le(p.x).unwrap();
            cursor.write_f32_le(p.y).unwrap();
            cursor.write_f32_le(p.z).unwrap();
            cursor.write_f32_le(r).unwrap();
            cursor.write_f32_le(g).unwrap();
            cursor.write_f32_le(b).unwrap();
            cursor.write_f32_le(1.0).unwrap(); // alpha
        }

        let pc = PointCloud {
            frame_id: pcd.header.frame_id.clone(),
            timestamp: Some(Timestamp::now()),
            pose: Some(Pose {
                position: Some(Vector3 { x: 0.0, y: 0.0, z: 0.0 }),
                orientation: Some(Quaternion { x: 0.0, y: 0.0, z: 0.0, w: 1.0 }),
            }),
            point_stride: 28,
            fields: vec![
                PackedElementField {
                    name: "x".into(),
                    offset: 0,
                    r#type: 7,
                },
                PackedElementField {
                    name: "y".into(),
                    offset: 4,
                    r#type: 7,
                },
                PackedElementField {
                    name: "z".into(),
                    offset: 8,
                    r#type: 7,
                },
                PackedElementField {
                    name: "rgba".into(),
                    offset: 12,
                    r#type: 7,
                },
            ],
            data: buffer,
        };

        log!("/pointcloud/clusters", pc);
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
        let _ = match rr_guard.log("/pointcloud/boxes3d", &rr_boxes) {
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

    thread::spawn(|| {
        WebSocketServer::new()
            .start_blocking()
            .expect("Server failed to start");
    });

    let cam_sub = session.declare_subscriber("rt/camera/h264").await.unwrap();
    task::spawn(camera_h264_handler(cam_sub));

    // let boxes2d_sub = session.declare_subscriber("rt/model/boxes2d").await.unwrap();
    // let boxes2d_rr = rr.clone();
    // let frame_size_boxes2d = frame_size.clone();
    // task::spawn(model_boxes2d_handler(boxes2d_sub, boxes2d_rr, frame_size_boxes2d));

    let lidar_sub = session.declare_subscriber("rt/lidar/clusters").await.unwrap();
    task::spawn(lidar_clusters_handler(lidar_sub));

    // let boxes3d_sub = session.declare_subscriber("rt/fusion/boxes3d").await.unwrap();
    // let boxes3d_rr = rr.clone();
    // task::spawn(fusion_boxes3d_handler(boxes3d_sub, boxes3d_rr));

    loop {
    }
}
