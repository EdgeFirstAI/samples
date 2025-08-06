use clap::Parser;
use edgefirst_samples::Args;
use edgefirst_schemas::foxglove_msgs::FoxgloveCompressedVideo;
use openh264::{decoder::Decoder, formats::YUVSource, nal_units};
use rerun::Image;
use std::{error::Error, sync::Arc};
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
        }
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    let (rr, _serve_guard) = args.rerun.init("camera-h264")?;
    let rr = Arc::new(Mutex::new(rr));

    let sub = session.declare_subscriber("rt/camera/h264").await.unwrap();
    let rr_clone = rr.clone();
    task::spawn(camera_h264_handler(sub, rr_clone));

    // Rerun setup
    loop {}
}
