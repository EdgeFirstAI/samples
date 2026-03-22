// SPDX-License-Identifier: Apache-2.0
// Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

use clap::Parser as _;
use edgefirst_samples::Args;
use edgefirst_schemas::edgefirst_msgs::RadarInfo;
use std::error::Error;

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let session = zenoh::open(args.clone()).await.unwrap();

    // Create a subscriber for "rt/radar/info"
    let subscriber = session.declare_subscriber("rt/radar/info").await.unwrap();

    let msg = subscriber.recv_async().await.unwrap();
    let bytes = msg.payload().to_bytes();
    let info = RadarInfo::from_cdr(&bytes)?;
    println!(
        "RadarInfo: center_frequency={} frequency_sweep={} cube={}",
        info.center_frequency(),
        info.frequency_sweep(),
        info.cube()
    );

    Ok(())
}
