// SPDX-License-Identifier: Apache-2.0
// Copyright © 2025 Au-Zone Technologies. All Rights Reserved.

use clap::Parser;
use serde_json::json;
use zenoh::config::{Config, WhatAmI};

#[derive(Parser, Debug, Clone)]
#[command(author, version, about, long_about = None)]
pub struct Args {
    /// Rerun parameters
    #[command(flatten)]
    pub rerun: rerun::clap::RerunArgs,

    /// zenoh connection mode
    #[arg(long, default_value = "peer")]
    pub mode: WhatAmI,

    /// connect to zenoh endpoints using the device hostname, not its IP
    /// address (e.g. --remote maivin-1234:7447), since topics are published
    /// under "<hostname>/<topic>" and the hostname is needed to find them
    #[arg(short, long)]
    pub remote: Vec<String>,

    /// listen to zenoh endpoints
    #[arg(short, long)]
    pub listen: Vec<String>,

    /// disable zenoh multicast scouting
    #[arg(long)]
    pub no_multicast_scouting: bool,
}

impl Args {
    /// Returns the topic prefix for this connection: the hostname parsed
    /// from the first `--remote` endpoint, or `*` to match any host when
    /// connecting locally.
    pub fn hostname(&self) -> String {
        match self.remote.first() {
            Some(endpoint) => {
                let host_port = endpoint.rsplit('/').next().unwrap_or(endpoint);
                host_port.split(':').next().unwrap_or(host_port).to_string()
            }
            None => "*".to_string(),
        }
    }
}

impl From<Args> for Config {
    fn from(args: Args) -> Self {
        let mut config = Config::default();

        config
            .insert_json5("mode", &json!(args.mode).to_string())
            .unwrap();

        if !args.remote.is_empty() {
            config
                .insert_json5("connect/endpoints", &json!(args.remote).to_string())
                .unwrap();
        }

        if !args.listen.is_empty() {
            config
                .insert_json5("listen/endpoints", &json!(args.listen).to_string())
                .unwrap();
        }

        if args.no_multicast_scouting {
            config
                .insert_json5("scouting/multicast/enabled", &json!(false).to_string())
                .unwrap();
        }

        config
            .insert_json5("scouting/multicast/interface", &json!("lo").to_string())
            .unwrap();

        config
    }
}
