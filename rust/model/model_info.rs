use clap::Parser as _;
use edgefirst_samples::Args;
use edgefirst_schemas::edgefirst_msgs::ModelInfo;
use std::{error::Error, sync::Arc};
use tokio::{sync::Mutex, task};
use zenoh::{handlers::FifoChannelHandler, pubsub::Subscriber, sample::Sample};

async fn model_info_handler(
    sub: Subscriber<FifoChannelHandler<Sample>>,
    rr: Arc<Mutex<rerun::RecordingStream>>,
) {
    while let Ok(msg) = sub.recv_async().await {
        let info = match cdr::deserialize::<ModelInfo>(&msg.payload().to_bytes()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to deserialize model info: {:?}", e);
                continue; // skip this message and continue
            }
        };

        let m_type = info.model_type;
        let m_name = info.model_name;
        let _input_shape = info.input_shape; // Input Shape
        let _input_type = info.input_type; // Input Type
        let _output_shape = info.output_shape; // Output Shape
        let _output_type = info.output_type; // Output Type
        let text = "Model Name: ".to_owned() + &m_name + " Model Type: " + &m_type;

        let rr_guard = rr.lock().await;
        let _ = match rr_guard.log("model/info", &rerun::TextLog::new(text)) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Failed to log model info: {:?}", e);
                continue; // skip this message and continue
            }
        };
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    let (rr, _serve_guard) = args.rerun.init("model-info")?;
    let rr = Arc::new(Mutex::new(rr));

    let sub = session.declare_subscriber("rt/model/info").await.unwrap();
    let rr_clone = rr.clone();
    task::spawn(model_info_handler(sub, rr_clone));

    // Rerun setup
    loop {
        
    }
}
