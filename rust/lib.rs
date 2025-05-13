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
    mode: WhatAmI,

    /// connect to zenoh endpoints
    #[arg(short, long)]
    remote: Vec<String>,

    /// listen to zenoh endpoints
    #[arg(short, long)]
    listen: Vec<String>,

    /// disable zenoh multicast scouting
    #[arg(long)]
    no_multicast_scouting: bool,
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
