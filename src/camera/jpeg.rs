use clap::Parser;
use edgefirst_schemas::sensor_msgs::CompressedImage;
use rerun::external::re_sdk_comms::DEFAULT_SERVER_PORT;
use std::net::{Ipv4Addr, SocketAddr};
use std::{error::Error, time::Instant};
use zenoh::Config;

#[derive(Parser, Debug, Clone)]
struct Args {
    /// Time in seconds to run command before exiting.
    #[arg(short, long)]
    pub timeout: Option<u64>,

    /// Connect to a Zenoh router rather than peer mode.
    #[arg(short, long)]
    connect: Option<String>,

    /// use this port for the rerun viewer (remote or web server)
    #[arg(short, long)]
    port: Option<u16>,

    /// Remote rerun viewer at this address
    #[arg(short, long)]
    remote: Option<Ipv4Addr>,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    // Start rerun recording
    let args = Args::parse();
    let rr = if let Some(addr) = args.remote {
        let port = args.port.unwrap_or(DEFAULT_SERVER_PORT);
        let remote = SocketAddr::new(addr.into(), port);
        Some(
            rerun::RecordingStreamBuilder::new("radarview")
                .connect_opts(remote, rerun::default_flush_timeout())?,
        )
    } else {
        None
    };

    let mut config = Config::default();
    if let Some(connect) = args.connect {
        config.insert_json5("mode", "client").unwrap();
        config.insert_json5("connect/endpoints", &connect).unwrap();
    }
    let session = zenoh::open(config).await.unwrap();

    let subscriber = session.declare_subscriber("rt/camera/jpeg").await.unwrap();
    let start = Instant::now();

    while let Ok(msg) = subscriber.recv() {
        if let Some(timeout) = args.timeout {
            if start.elapsed().as_secs() >= timeout {
                break;
            }
        }

        let img: CompressedImage = cdr::deserialize(&msg.payload().to_bytes())?;
        println!("Received message: {:?}", img);
        let jpeg_bytes = img.data;
        if let Some(rr) = &rr {
            rr.log(
                "image",
                &rerun::EncodedImage::from_file_contents(jpeg_bytes.to_vec()),
            )?;
        }
    }

    Ok(())
}
