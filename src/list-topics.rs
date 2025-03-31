use clap::Parser;
use std::{collections::HashSet, time::Instant};
use zenoh::Config;

#[derive(Parser, Debug, Clone)]
struct Args {
    /// Time in seconds to run command before exiting.
    #[arg(short, long)]
    pub timeout: Option<u64>,

    /// Connect to a Zenoh router rather than peer mode.
    #[arg(short, long)]
    connect: Option<String>,
}

#[tokio::main]
async fn main() {
    let args = Args::parse();

    // Create the default Zenoh configuration and if the connect argument is
    // provided set the mode to client and add the target to the endpoints.
    let mut config = Config::default();
    if let Some(connect) = args.connect {
        config.insert_json5("mode", "client").unwrap();
        config.insert_json5("connect/endpoints", &connect).unwrap();
    }
    let session = zenoh::open(config).await.unwrap();

    // Create a subscriber for all topics matching the pattern "rt/**"
    let subscriber = session.declare_subscriber("rt/**").await.unwrap();

    // Keep a list of discovered topics to avoid noise from duplicates
    let mut topics = HashSet::new();
    let start = Instant::now();

    while let Ok(msg) = subscriber.recv() {
        if let Some(timeout) = args.timeout {
            if start.elapsed().as_secs() >= timeout {
                break;
            }
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
}
