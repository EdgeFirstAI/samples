import os
import sys
from argparse import ArgumentParser, RawTextHelpFormatter

import numpy as np
import rerun as rr
from PIL import Image

def load_model(model_path: str, delegate: str):
    if os.path.splitext(os.path.basename(model_path))[-1] == ".tflite":

        from tflite_runtime.interpreter import (  # type: ignore
            Interpreter,
            load_delegate
        )
        if delegate and os.path.exists(delegate) and delegate.endswith(".so"):
            ext_delegate = load_delegate(delegate, {})
            model = Interpreter(model_path, experimental_delegates=[ext_delegate])
        else:
            model = Interpreter(model_path)

        # Loading the model
        model.allocate_tensors()

        # Get input and output tensors.
        input_details = model.get_input_details()
        output_details = model.get_output_details()

        # Bounding boxes (xmin, ymin, xmax, ymax). Shape must be (1, NB, 1, 4)
        box_details = output_details[0]
        score_details = output_details[1]  # Scores. Shape must be (1, NB, 1)

        print("Input shape: ", input_details[0]['shape'])
        print("Boxes Output shape: ", output_details[0]['shape'])
        print("Scores Output shape: ", output_details[1]['shape'])

        return model

def run_tflite_inference(model, input: np.ndarray):
    H, W = model.get_input_details()[0]['shape'][1:3]
    image = Image.fromarray(input)
    image.resize((W, H))
    input = np.array(image).astype(np.uint8) # TFLite is quantized with uint8 input.

def login(username: str, password: str, server: str, session_id: str, model_path: str):
    """
    Only login to EdgeFirst Client if the model and labels.txt does not
    exist and the client is needed to fetch the artifacts. 
    """
    from edgefirst_client import Client
    client = Client(server)
    client.login_sync(username, password)

    if session_id.startswith('t-') or session_id.startswith('v-'):
        session_id = int(session_id.split('-')[-1], 16)
    else:
        session_id = int(session_id)

    client.download_artifact_sync(session_id, model_path, filename=os.path.basename(model_path))
    client.download_artifact_sync(session_id, 'labels.txt', filename='labels.txt')


def main():
    args = ArgumentParser(description="EdgeFirst Samples - Deploying Modelpack", 
                          formatter_class=RawTextHelpFormatter)
    args.add_argument('-u', '--username', type=str, default=None,
                    help=("Specify EdgeFirst Studio username. "
                        "Optionally using the edgefirst-client to fetch the artifacts."))
    args.add_argument('-p', '--password', type=str, default=None,
                    help=("Specify EdgeFirst Studio password. "
                        "Optionally using the edgefirst-client to fetch the artifacts."))
    args.add_argument('-s', '--server', type=str, default='saas',
                    help=("Specify EdgeFirst Studio password. "
                        "Optionally using the edgefirst-client to fetch the artifacts."))
    args.add_argument('-t', '--trainer', type=str,
                    help="Specify trainer session ID to fetch model artifacts.")
    args.add_argument('-m', '--model', type=str, required=True,
                      help=("Specify the path to the model or the model to download. "
                            "Examples include modelpack.tflite, modelpack.onnx"))
    args.add_argument('-l', '--labels', type=str, default='labels.txt',
                      help=("Specify the path to the labels.txt to map label "
                            "indices to string."))
    args.add_argument('-d', '--delegate', type=str, default='/usr/lib/libvx_delegate.so',
                      help="Specify the path to the NPU delegate for the TFLite. ")
    # rr.script_add_args(args)
    args = args.parse_args()

    # rr.script_setup(args, "modelpack")

    model_path = args.model
    if model_path and not os.path.exists(model_path):
        print(f"Warning: The model {model_path} does not exist. Attempting to download...")

        if None in [args.username, args.password]:
            raise ValueError("Please specify your EdgeFirst Studio username and password.")
        
        if args.trainer is None:
            raise ValueError("Please specify the training session ID to fetch artifacts.")
            
        login(args.username, args.password, args.server, args.trainer, model_path)

    model = load_model(model_path, args.delegate)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)