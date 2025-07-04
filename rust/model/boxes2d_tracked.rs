use clap::Parser as _;
use edgefirst_samples::Args;
use edgefirst_schemas::edgefirst_msgs::Detect;
use std::{error::Error, sync::Arc};
use std::collections::HashMap;
use rand::{rng, Rng};
use rerun::{Boxes2D};
use tokio::{sync::Mutex, task};
use zenoh::{handlers::FifoChannelHandler, pubsub::Subscriber, sample::Sample};

async fn model_boxes2d_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>,
    rr: Arc<Mutex<rerun::RecordingStream>>,
) {
    let mut boxes_tracked: HashMap<String, (String, [u8; 3])> = HashMap::new();

    while let Ok(msg) = sub.recv_async().await {
        let detection = match cdr::deserialize::<Detect>(&msg.payload().to_bytes()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize model boxes2d: {:?}", e);
                continue; // skip this message and continue
            }
        };

        let mut centers = Vec::new();
        let mut sizes = Vec::new();
        let mut labels = Vec::new();
        let mut colors = Vec::new();

        for b in detection.boxes {
            if !b.track.id.is_empty() {
                // Insert into map if not already present
                let entry = boxes_tracked.entry(b.track.id.clone()).or_insert_with(|| {
                    let mut rng_maker = rng();
                    let random_color = [
                        rng_maker.random_range(0..=255),
                        rng_maker.random_range(0..=255),
                        rng_maker.random_range(0..=255),
                    ];
                    let short_id = &b.track.id[..6.min(b.track.id.len())];
                    let label = format!("{}: {}", b.label, short_id);
                    (label, random_color)
                });

                labels.push(entry.0.clone());
                colors.push(entry.1);
            } else {
                labels.push(b.label.clone());
                colors.push([0, 255, 0]);
            }

            centers.push([b.center_x, b.center_y]);
            sizes.push([b.width, b.height]);
        }
        let boxes = Boxes2D::from_centers_and_sizes(centers, sizes)
            .with_labels(labels)
            .with_colors(colors);

        let rr_guard = rr.lock().await;
        let _ = match rr_guard.log("model/boxes", &boxes) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to log boxes: {:?}", e);
                continue; // skip this message and continue
            }
        };
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    let (rr, _serve_guard) = args.rerun.init("model-boxes2d")?;
    let rr = Arc::new(Mutex::new(rr));

    let sub = session.declare_subscriber("rt/model/boxes2d").await.unwrap();
    let rr_clone = rr.clone();
    task::spawn(model_boxes2d_handler(sub, rr_clone));

    // Rerun setup
    loop {
        
    }
}
