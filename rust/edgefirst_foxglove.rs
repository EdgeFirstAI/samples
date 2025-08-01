use std::{
    error::Error,
    sync::Arc,
    thread,
    collections::HashMap
};
use clap::Parser;
use bytes::Bytes;
use edgefirst_samples::Args;
use edgefirst_schemas::{
    decode_pcd, 
    edgefirst_msgs::Detect, 
    foxglove_msgs::FoxgloveCompressedVideo, 
    geometry_msgs::TransformStamped, 
    sensor_msgs::{NavSatFix, PointCloud2, IMU}
};
use foxglove::{WebSocketServer, log,
    schemas::{Timestamp, CompressedVideo, PointCloud, PackedElementField,
              Quaternion, Vector3, Pose, Color, CubePrimitive, SceneEntity, SceneEntityDeletion,
              SceneUpdate, FrameTransform, TextAnnotation, ImageAnnotations, Point2,
              PointsAnnotation, LocationFix}
};
use openh264::{decoder::Decoder, formats::YUVSource, nal_units};
use tokio::{sync::Mutex, task};
use zenoh::{handlers::FifoChannelHandler, pubsub::Subscriber, sample::Sample};

async fn camera_h264_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>,
    frame_size: Arc<Mutex<[u32; 2]>>,
) {
    let mut decoder = Decoder::new().expect("Failed to create decoder");

    while let Ok(msg) = sub.recv_async().await {
        let video = match cdr::deserialize::<FoxgloveCompressedVideo>(&msg.payload().to_bytes()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize video: {:?}", e);
                continue;
            }
        };
        let mut size = frame_size.lock().await;
        if size[0] == 0 || size[1] == 0 {
            for packet in nal_units(&video.data) {
                let Ok(Some(yuv)) = decoder.decode(packet) else { continue };
                let width = yuv.dimensions().0;
                let height = yuv.dimensions().1;
                *size = [width as u32, height as u32];
            }
        }

        let ts = Timestamp::new(video.header.stamp.sec as u32, video.header.stamp.nanosec);
        let cv = CompressedVideo {
            timestamp: Some(ts.clone()),
            frame_id: video.header.frame_id.clone(),
            data: video.data.clone().into(),
            format: video.format.clone(),
        };
        log!("/camera", cv)
    }
}

async fn model_boxes2d_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>,
    frame_size: Arc<Mutex<[u32; 2]>>,
) {
    let mut boxes_tracked: HashMap<String, Color> = HashMap::new();
    while let Ok(msg) = sub.recv_async().await {
        let detection = match cdr::deserialize::<Detect>(&msg.payload().to_bytes()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize detect message: {:?}", e);
                continue; // skip this message and continue
            }
        };

        let ts = Timestamp::new(detection.header.stamp.sec as u32, detection.header.stamp.nanosec);
        let mut point_annos = vec![];
        let mut label_annos = vec![];
        let size = frame_size.lock().await;
        if size[0] == 0 || size[1] == 0 { continue; }
        let w = size[0] as f64;
        let h = size[1] as f64;
        for b in detection.boxes {

            let mut lx = b.center_x as f64 * w - (b.width as f64 * w / 2.0);
            lx = lx.clamp(0.0, w);

            let mut rx = b.center_x as f64 * w + (b.width as f64 * w / 2.0);
            rx = rx.clamp(0.0, w);

            let mut uy = b.center_y as f64 * h - (b.height as f64 * h / 2.0);
            uy = uy.clamp(0.0, h);

            let mut by = b.center_y as f64 * h + (b.height as f64 * h / 2.0);
            by = by.clamp(0.0, h);

            let mut color = Color { r: 0.0, g: 1.0, b: 0.0, a: 1.0 };
            let mut label = TextAnnotation {
                timestamp: Some(ts.clone()),
                position: Some(Point2 { x: lx, y: by }),
                text: b.label.clone(),
                font_size: 32.0,
                text_color: Some(Color { r: 0.0, g: 0.0, b: 0.0, a: 1.0 }),
                background_color: Some(Color { r: 1.0, g: 1.0, b: 1.0, a: 1.0 }),
            };

            if b.track.id != "" {
                if !boxes_tracked.contains_key(&b.track.id) {
                    let rgb = (
                        rand::random::<u8>(),
                        rand::random::<u8>(),
                        rand::random::<u8>()
                    );
                    boxes_tracked.insert(
                        b.track.id.clone(),
                        Color {
                            r: rgb.0 as f64 / 255.0,
                            g: rgb.1 as f64 / 255.0,
                            b: rgb.2 as f64 / 255.0,
                            a: 1.0,
                        },
                    );
                }
                color = boxes_tracked[&b.track.id];
                let short_id = &b.track.id[0..6];
                label = TextAnnotation {
                    timestamp: Some(ts.clone()),
                    position: Some(Point2 { x: lx, y: by }),
                    text: format!("{}: {}", b.label, short_id),
                    font_size: 32.0,
                    text_color: Some(Color { r: 1.0, g: 1.0, b: 1.0, a: 1.0 }),
                    background_color: Some(Color { r: 0.0, g: 0.0, b: 0.0, a: 1.0 }),
                };
            }

            label_annos.push(label);

            let points = vec![
                Point2 { x: lx, y: uy },
                Point2 { x: lx, y: by },
                Point2 { x: rx, y: by },
                Point2 { x: rx, y: uy },
            ];

            point_annos.push(PointsAnnotation {
                timestamp: Some(ts.clone()),
                r#type: 2,
                points: points,
                outline_color: Some(color),
                thickness: 5.0,
                ..Default::default()
            });
        }

        let annotations = ImageAnnotations {
            points: point_annos,
            texts: label_annos,
            ..Default::default()
        };
        log!("/camera/boxes2d", annotations);
        
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

        let mut packed = Vec::with_capacity(clustered_points.len() * 28); // 7 f32 values per point

        for p in &clustered_points {
            let (r, g, b) = colorous::TURBO
                .eval_continuous(p.id as f64 / max_cluster_id as f64)
                .as_tuple();

            // Normalize u8 RGB to 0.0–1.0
            let r = r as f32 / 255.0;
            let g = g as f32 / 255.0;
            let b = b as f32 / 255.0;

            packed.push(p.x as f32);
            packed.push(p.y as f32);
            packed.push(p.z as f32);
            packed.push(r);
            packed.push(g);
            packed.push(b);
            packed.push(1.0 as f32);
        }

        let data = Bytes::from(bytemuck::cast_slice(&packed).to_vec());

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
            data: data,
        };

        log!("/pointcloud/lidar/clusters", pc);
    }
}

async fn radar_clusters_handler(
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

        let mut packed = Vec::with_capacity(clustered_points.len() * 28); // 7 f32 values per point

        for p in &clustered_points {
            let (r, g, b) = colorous::TURBO
                .eval_continuous(p.id as f64 / max_cluster_id as f64)
                .as_tuple();

            // Normalize u8 RGB to 0.0–1.0
            let r = r as f32 / 255.0;
            let g = g as f32 / 255.0;
            let b = b as f32 / 255.0;

            packed.push(p.x as f32);
            packed.push(p.y as f32);
            packed.push(p.z as f32);
            packed.push(r);
            packed.push(g);
            packed.push(b);
            packed.push(1.0 as f32);
        }

        let data = Bytes::from(bytemuck::cast_slice(&packed).to_vec());

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
            data: data,
        };

        log!("/pointcloud/radar/clusters", pc);
    }
}

async fn fusion_boxes3d_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>
) {
    while let Ok(msg) = sub.recv_async().await {
        let det = match cdr::deserialize::<Detect>(&msg.payload().to_bytes()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize fusion_boxes3d: {:?}", e);
                continue; // skip this message and continue
            }
        };
        // Timestamp from header
        let ts = Timestamp::new(det.header.stamp.sec as u32, det.header.stamp.nanosec);

        // Convert each box to CubePrimitive
        let cubes: Vec<CubePrimitive> = det
            .boxes
            .iter()
            .map(|b| CubePrimitive {
                pose: Some(Pose {
                    position: Some(Vector3 {
                        x: b.center_x as f64,
                        y: b.center_y as f64,
                        z: b.distance as f64,
                    }),
                    orientation: Some(Quaternion {
                        x: 0.0,
                        y: 0.0,
                        z: 0.0,
                        w: 1.0,
                    }),
                }),
                size: Some(Vector3 {
                    x: b.width as f64,
                    y: b.height as f64,
                    z: b.width as f64,
                }),
                color: Some(Color {
                    r: 0.0,
                    g: 1.0,
                    b: 0.0,
                    a: 0.5,
                }),
            })
            .collect();

        // Create the entity with the cubes
        let entity = SceneEntity {
            timestamp: Some(ts.clone()),
            frame_id: det.header.frame_id.clone(),
            id: "boxes3d".to_string(),
            cubes: cubes,
            ..Default::default()
        };

        // Log the update with a matching deletion
        let update = SceneUpdate {
            deletions: vec![SceneEntityDeletion {
                timestamp: Some(ts.clone()),
                r#type: 0,
                id: "boxes3d".to_string(),
            }],
            entities: vec![entity],
        };

        log!("/pointcloud/boxes3d", update);
    }
}

async fn gps_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>,
) {
    while let Ok(msg) = sub.recv_async().await {
        let gps = match cdr::deserialize::<NavSatFix>(&msg.payload().to_bytes()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize gps: {:?}", e);
                continue; // skip this message and continue
            }
        };

        let ts = Timestamp::new(gps.header.stamp.sec as u32, gps.header.stamp.nanosec);
        let loc_fix = LocationFix {
            timestamp: Some(ts.clone()),
            frame_id: gps.header.frame_id,
            latitude: gps.latitude,
            longitude: gps.longitude,
            altitude: gps.altitude,
            position_covariance: gps.position_covariance.to_vec(),
            position_covariance_type: gps.position_covariance_type as i32
        };

        log!("/gps", loc_fix);
    }
}

async fn imu_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>,
) {
    while let Ok(msg) = sub.recv_async().await {
        let imu = match cdr::deserialize::<IMU>(&msg.payload().to_bytes()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize imu: {:?}", e);
                continue; // skip this message and continue
            }
        };
        let imu_quat = Quaternion {
            x: imu.orientation.x,
            y: imu.orientation.y,
            z: imu.orientation.z,
            w: imu.orientation.w
        };
        let imu_angular_vel = Vector3 {
            x: imu.angular_velocity.x,
            y: imu.angular_velocity.y,
            z: imu.angular_velocity.z
        };
        let imu_linear_accel = Vector3 {
            x: imu.linear_acceleration.x,
            y: imu.linear_acceleration.y,
            z: imu.linear_acceleration.z
        };
        log!("/imu/quaternion", imu_quat);
        log!("/imu/angular_velocity", imu_angular_vel);
        log!("/imu/linear_acceleration", imu_linear_accel);
    }
}

async fn static_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>
 ) {
    while let Ok(msg) = sub.recv_async().await {
        let tf_static = match cdr::deserialize::<TransformStamped>(&msg.payload().to_bytes()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize tf_static: {:?}", e);
                continue; // skip this message and continue
            }
        };
        let ts = Timestamp::new(tf_static.header.stamp.sec as u32, tf_static.header.stamp.nanosec);

        let transform = FrameTransform {
            timestamp: Some(ts.clone()),
            parent_frame_id: tf_static.header.frame_id.clone(),
            child_frame_id: tf_static.child_frame_id.clone(),
            translation: Some(Vector3 {
                x: tf_static.transform.translation.x,
                y: tf_static.transform.translation.y,
                z: tf_static.transform.translation.z,
            }),
            rotation: Some(Quaternion {
                x: tf_static.transform.rotation.x,
                y: tf_static.transform.rotation.y,
                z: tf_static.transform.rotation.z,
                w: tf_static.transform.rotation.w,
            }),
        };

        log!("/tf_static", transform);
    }
 }

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();
    let frame_size = Arc::new(Mutex::new([0u32; 2]));

    thread::spawn(|| {
        WebSocketServer::new().bind("0.0.0.0", 8765)
            .start_blocking()
            .expect("Server failed to start");
    });
    
    let cam_sub = session.declare_subscriber("rt/camera/h264").await.unwrap();
    let frame_size_cam = frame_size.clone();
    task::spawn(camera_h264_handler(cam_sub, frame_size_cam));

    let boxes2d_sub = session.declare_subscriber("rt/model/boxes2d").await.unwrap();
    let frame_size_boxes2d = frame_size.clone();
    task::spawn(model_boxes2d_handler(boxes2d_sub, frame_size_boxes2d));

    let lidar_sub = session.declare_subscriber("rt/lidar/clusters").await.unwrap();
    task::spawn(lidar_clusters_handler(lidar_sub));

    let lidar_sub = session.declare_subscriber("rt/radar/clusters").await.unwrap();
    task::spawn(radar_clusters_handler(lidar_sub));

    let boxes3d_sub = session.declare_subscriber("rt/fusion/boxes3d").await.unwrap();
    task::spawn(fusion_boxes3d_handler(boxes3d_sub));

    let gps_sub = session.declare_subscriber("rt/gps").await.unwrap();
    task::spawn(gps_handler(gps_sub));

    let imu_sub = session.declare_subscriber("rt/imu").await.unwrap();
    task::spawn(imu_handler(imu_sub));

    let static_sub = session.declare_subscriber("rt/tf_static").await.unwrap();
    task::spawn(static_handler(static_sub));

    loop {
    }
}
