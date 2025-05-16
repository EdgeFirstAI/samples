use clap::Parser as _;
use edgefirst_samples::Args;
use edgefirst_schemas::edgefirst_msgs::ModelInfo;
use std::error::Error;

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    // Create a subscriber for "rt/model/info"
    let subscriber = session.declare_subscriber("rt/model/info").await.unwrap();

    // Create Rerun logger using the provided parameters
    let (rr, _serve_guard) = args.rerun.init("model-info")?;

    while let Ok(msg) = subscriber.recv() {
        let info: ModelInfo = cdr::deserialize(&msg.payload().to_bytes())?;

        let m_type = info.model_type;
        let m_name = info.model_name;
        let _input_shape = info.input_shape; // Input Shape
        let _input_type = info.input_type; // Input Type
        let _output_shape = info.output_shape; // Output Shape
        let _output_type = info.output_type; // Output Type
        let text = "Model Name: ".to_owned() + &m_name.to_string() + " Model Type: " + &m_type.to_string();
        let _ = rr.log("ModelInfo", &rerun::TextLog::new(text));
    }

    Ok(())
}
