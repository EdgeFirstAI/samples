use clap::Parser;
use rerun::{
    archetypes::Image, external::re_sdk_comms::DEFAULT_SERVER_PORT, RecordingStreamBuilder,
};
use serde_json;
use std::net::{Ipv4Addr, SocketAddr};
use zenoh::{config::Config, open, Session};

#[derive(Parser, Debug, Clone)]
#[command(author, version, about, long_about = None)]
struct Args {
    /// connect to remote rerun viewer at this address
    #[arg(short, long)]
    connect: Option<Ipv4Addr>,

    /// record rerun data to file instead of live viewer
    #[arg(short, long)]
    record: Option<String>,

    /// launch local rerun viewer
    #[arg(short, long)]
    viewer: bool,

    /// use this port for the rerun viewer (remote or web server)
    #[arg(short, long)]
    port: Option<u16>,

    /// connect to zenoh endpoints
    #[arg(short, long)]
    zenoh_connect: Vec<String>,
}

fn find_jpeg_start(bytes: &[u8]) -> Option<usize> {
    // JPEG start marker is 0xFF, 0xD8
    for i in 0..bytes.len().saturating_sub(1) {
        if bytes[i] == 0xFF && bytes[i + 1] == 0xD8 {
            return Some(i);
        }
    }
    None
}

#[tokio::main]
async fn main() -> Result<(), anyhow::Error> {
    let args = Args::parse();
    println!("Starting JPEG viewer with args: {:?}", args);

    // Rerun recorder
    let rr = if let Some(addr) = args.connect {
        println!("Connecting to remote viewer at {}", addr);
        let port = args.port.unwrap_or(DEFAULT_SERVER_PORT);
        let remote = SocketAddr::new(addr.into(), port);
        Some(
            RecordingStreamBuilder::new("jpeg_viewer")
                .connect_tcp_opts(remote, rerun::default_flush_timeout())?,
        )
    } else if let Some(record) = args.record {
        println!("Recording to file: {}", record);
        Some(RecordingStreamBuilder::new("jpeg_viewer").save(record)?)
    } else if args.viewer {
        println!("Launching local viewer");
        Some(RecordingStreamBuilder::new("jpeg_viewer").spawn()?)
    } else {
        println!("No viewer specified");
        None
    };

    // Zenoh config
    let mut config = Config::default();
    if !args.zenoh_connect.is_empty() {
        println!("Configuring Zenoh with endpoints: {:?}", args.zenoh_connect);
        let mode = "\"client\"";
        println!("Setting mode to: {}", mode);
        config
            .insert_json5("mode", mode)
            .map_err(|e| anyhow::anyhow!("Failed to set Zenoh mode: {}", e))?;

        let endpoints = serde_json::to_string(&args.zenoh_connect)
            .map_err(|e| anyhow::anyhow!("Failed to serialize endpoints: {}", e))?;
        println!("Setting endpoints to: {}", endpoints);
        config
            .insert_json5("connect/endpoints", &endpoints)
            .map_err(|e| anyhow::anyhow!("Failed to set Zenoh endpoints: {}", e))?;
    }

    println!("Opening Zenoh session...");
    // Open Zenoh session & subscriber
    let session: Session = open(config)
        .await
        .map_err(|e| anyhow::anyhow!("Failed to open Zenoh session: {}", e))?;
    println!("Zenoh session opened successfully");

    println!("Creating subscriber for 'rt/camera/jpeg'...");
    let subscriber = session
        .declare_subscriber("rt/camera/jpeg")
        .await
        .map_err(|e| anyhow::anyhow!("Failed to create subscriber: {}", e))?;
    println!("Subscriber created successfully");

    // Receive and process compressed messages
    println!("Waiting for messages...");
    while let Ok(sample) = subscriber.recv_async().await {
        let payload = sample.payload();
        let bytes = payload.to_bytes();
        println!("Received message with length: {}", bytes.len());

        // Print first 32 bytes for debugging
        println!(
            "First 32 bytes: {:02X?}",
            &bytes[..std::cmp::min(32, bytes.len())]
        );

        // Find JPEG start marker
        if let Some(start_pos) = find_jpeg_start(&bytes) {
            println!("Found JPEG start marker at position {}", start_pos);
            let jpeg_data = &bytes[start_pos..];

            if let Some(rr) = &rr {
                // Log as JPEG image to Rerun
                let image =
                    Image::from_image_bytes(rerun::external::image::ImageFormat::Jpeg, jpeg_data)?;
                rr.log("camera/frame", &image)?;
                rr.flush_blocking();
            }
        } else {
            println!("No JPEG start marker found in the data");
        }
    }

    Ok(())
}
