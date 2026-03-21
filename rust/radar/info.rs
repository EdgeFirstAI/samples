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

    let msg = subscriber.recv().unwrap();
    let bytes = msg.payload().to_bytes();
    let _info = RadarInfo::from_cdr(&bytes)?;

    // Note: RadarInfo doesn't implement Debug in 2.0.1
    // println!("{:?}", _info);
    println!("Received RadarInfo message");

    Ok(())
}
