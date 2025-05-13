use clap::Parser as _;
use edgefirst_samples::Args;
use std::{collections::HashSet, error::Error, time::Instant};

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    // Create a subscriber for all topics matching the pattern "rt/**"
    let subscriber = session.declare_subscriber("rt/**").await.unwrap();

    // Keep a list of discovered topics to avoid noise from duplicates
    let mut topics = HashSet::new();
    let start = Instant::now();

    while let Ok(msg) = subscriber.recv() {
        if start.elapsed().as_secs() >= 5 {
            break;
        }

        // Ignore message if the topic is known otherwise save the topic
        if topics.contains(msg.key_expr().as_str()) {
            continue;
        }
        topics.insert(msg.key_expr().to_string());

        // Capture the message encoding MIME type then split on the first ';' to get the schema
        let schema = msg.encoding().to_string();
        let schema = schema.splitn(2, ';').last().unwrap_or_default();
        println!("topic: {} → {}", msg.key_expr(), schema);
    }

    Ok(())
}
