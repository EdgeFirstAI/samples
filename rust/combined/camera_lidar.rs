use std::{
    error::Error,
    sync::Arc
};
use clap::Parser;
use edgefirst_samples::Args;
use edgefirst_schemas::{
    decode_pcd,
    edgefirst_msgs::Detect,
    foxglove_msgs::FoxgloveCompressedVideo,
    sensor_msgs::{PointCloud2},
};
use openh264::{decoder::Decoder, formats::YUVSource, nal_units};
use rerun::{Boxes3D, Color, Image, Points3D, Position3D};
use tokio::{sync::Mutex, task};
use zenoh::{handlers::FifoChannelHandler, pubsub::Subscriber, sample::Sample};

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
                eprintln!("Failed to deserialize video: {:?}", e);
                continue;
            }
        };

        for packet in nal_units(&video.data) {
            let Ok(Some(yuv)) = decoder.decode(packet) else { continue };
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
        let _ = match rr_guard.log("/pointcloud/lidar", &points) {
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

    let (rr, _serve_guard) = args.rerun.init("camera-lidar")?;
    let rr = Arc::new(Mutex::new(rr));
    let frame_size = Arc::new(Mutex::new([0u32; 2]));

    let cam_sub = session.declare_subscriber("rt/camera/h264").await.unwrap();
    let cam_rr = rr.clone();
    let frame_size_cam = frame_size.clone();
    task::spawn(camera_h264_handler(cam_sub, cam_rr, frame_size_cam));

    let boxes2d_sub = session.declare_subscriber("rt/model/boxes2d").await.unwrap();
    let boxes2d_rr = rr.clone();
    let frame_size_boxes2d = frame_size.clone();
    task::spawn(model_boxes2d_handler(boxes2d_sub, boxes2d_rr, frame_size_boxes2d));

    let lidar_sub = session.declare_subscriber("rt/lidar/clusters").await.unwrap();
    let lidar_rr = rr.clone();
    task::spawn(lidar_clusters_handler(lidar_sub, lidar_rr));

    let boxes3d_sub = session.declare_subscriber("rt/fusion/boxes3d").await.unwrap();
    let boxes3d_rr = rr.clone();
    task::spawn(fusion_boxes3d_handler(boxes3d_sub, boxes3d_rr));

    loop {
    }
}
