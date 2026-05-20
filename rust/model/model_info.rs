// SPDX-License-Identifier: Apache-2.0
// Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

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

    while let Ok(msg) = subscriber.recv_async().await {
        let bytes = msg.payload().to_bytes();
        let info = ModelInfo::from_cdr(&bytes)?;

        let text = format!(
            "Model Name: {} Model Type: {} Input: {:?}x{} Output: {:?}x{}",
            info.model_name(),
            info.model_type(),
            info.input_shape(),
            info.input_type(),
            info.output_shape(),
            info.output_type(),
        );
        rr.log("ModelInfo", &rerun::TextLog::new(text))?;
    }

    Ok(())
}
