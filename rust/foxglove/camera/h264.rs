use std::{error::Error, sync::Arc, thread};
use clap::Parser;
use edgefirst_samples::Args;
use edgefirst_schemas::foxglove_msgs::FoxgloveCompressedVideo;
// use openh264::{decoder::Decoder, formats::YUVSource, nal_units};
use tokio::{sync::Mutex, task};
use zenoh::{handlers::FifoChannelHandler, pubsub::Subscriber, sample::Sample};
use foxglove::{WebSocketServer, log,
    schemas::{Timestamp, CompressedVideo}
};

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


#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    thread::spawn(|| {
        WebSocketServer::new()
            .start_blocking()
            .expect("Server failed to start");
    });

    let sub = session.declare_subscriber("rt/camera/h264").await.unwrap();
    task::spawn(camera_h264_handler(sub));

    // Rerun setup
    loop {
        
    }
}

