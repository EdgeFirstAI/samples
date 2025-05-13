import os
import sys
from argparse import ArgumentParser, RawTextHelpFormatter

import numpy as np
from PIL import Image
import rerun as rr

# Note autopep8 and other auto-formatters can break this piece of code so we
# include a comment of the appropriate layout for reference.  This is required
# by the GObject Introspection for Python library.
#
# https://pygobject.readthedocs.io/
#
# import gi
# gi.require_version("Gst", "1.0")
# gi.require_version("GstApp", "1.0")
# from gi.repository import Gst, GstApp, GLib
#
import gi  # type: ignore
gi.require_version("Gst", "1.0")
gi.require_version("GstApp", "1.0")
from gi.repository import Gst, GstApp, GLib  # type: ignore

class Model:

    def __init__(
        self,
        iou_threshold: float = 0.50,
        score_threshold: float = 0.25,
    ):
        self.iou_threshold = iou_threshold
        self.score_threshold = score_threshold
        self.shape = None  # Model input shape [height, width]
        self.with_masks = True
        self.with_boxes = True
        self.labels = None
        self.model = None
        self.frame_id = 0

    def load_labels(self, labels_path: str):
        # Loading the labels to assign to bounding boxes
        if os.path.exists(labels_path):
            with open(labels_path, 'r') as f:
                labels = f.readlines()
            self.labels = [label.strip() for label in labels]

    def load_model(
        self,
        model_path: str,
        delegate: str = "/usr/lib/libvx_delegate.so"
    ):
        self.model_path = model_path
        if os.path.splitext(os.path.basename(model_path))[-1] == ".tflite":
            self.model = self.load_tflite_model(model_path, delegate)
        elif os.path.splitext(os.path.basename(model_path))[-1] == ".onnx":
            self.model = self.load_onnx_model(model_path)
        else:
            raise NotImplementedError(
                f"This model {model_path} is currently not supported.")

    def run_model(self, inputs: np.ndarray):
        height, width = self.shape
        image = Image.fromarray(inputs)
        image = image.resize((width, height))
        # TFLite is quantized with uint8 input.
        inputs = np.expand_dims(np.array(image).astype(np.uint8), 0)

        if os.path.splitext(os.path.basename(self.model_path))[-1] == ".tflite":
            return self.run_tflite(inputs)
        elif os.path.splitext(os.path.basename(self.model_path))[-1] == ".onnx":
            return self.run_onnx(inputs)
        else:
            raise NotImplementedError(
                f"This model {self.model_path} is currently not supported.")

    def load_tflite_model(self, model_path: str, delegate: str):
        from tflite_runtime.interpreter import (  # type: ignore
            Interpreter,
            load_delegate
        )
        if delegate and os.path.exists(delegate) and delegate.endswith(".so"):
            ext_delegate = load_delegate(delegate, {})
            model = Interpreter(
                model_path, experimental_delegates=[ext_delegate])
        else:
            model = Interpreter(model_path)

        # Loading the model
        model.allocate_tensors()

        # Get input and output tensors.
        input_details = model.get_input_details()
        output_details = model.get_output_details()

        # return [height, width]
        self.shape = input_details[0]['shape'][1:3]

        # 3 outputs => multi-task
        if len(output_details) > 2:
            self.with_boxes = True
            self.with_masks = True
        # 2 outputs => detection
        elif len(output_details) > 1:
            self.with_boxes = True
            self.with_masks = False
        # 1 outputs => segmentation
        else:
            self.with_boxes = False
            self.with_masks = True

        return model

    def run_tflite(self, inputs: np.ndarray):
        input_details = self.model.get_input_details()
        output_details = self.model.get_output_details()

        inputs = np.array(inputs, dtype=np.uint8)
        self.model.set_tensor(input_details[0]['index'], inputs)
        self.model.invoke()

        box_details, mask_details, score_details = None, None, None
        boxes, classes, scores, masks = None, None, None, None

        for output in output_details:
            if len(output["shape"]) == 4:
                if output["shape"][-2] == 1:
                    box_details = output
                else:
                    mask_details = output
            else:
                score_details = output

        if box_details and score_details:
            outputs_boxes = self.model.get_tensor(box_details["index"])
            outputs_scores = self.model.get_tensor(score_details["index"])

            if box_details["dtype"] != np.float32:
                scale, zero_point = box_details["quantization"]
                outputs_boxes = (outputs_boxes.astype(
                    np.float32) - zero_point) * scale  # re-scale

            if score_details["dtype"] != np.float32:
                scale, zero_point = score_details["quantization"]
                outputs_scores = (outputs_scores.astype(
                    np.float32) - zero_point) * scale  # re-scale

            boxes, classes, scores = self.nms(
                outputs_boxes,
                outputs_scores,
                iou_threshold=self.iou_threshold,
                score_threshold=self.score_threshold
            )

        if mask_details:
            masks = self.model.get_tensor(mask_details["index"])

            if mask_details["dtype"] != np.float32:
                scale, zero_point = mask_details["quantization"]
                masks = (masks.astype(np.float32) -
                         zero_point) * scale  # re-scale

        if self.with_boxes and self.with_masks:
            return boxes, classes, scores, masks
        elif self.with_boxes:
            return boxes, classes, scores
        return masks

    def load_onnx_model(self, model_path: str):
        import onnxruntime  # type: ignore

        providers = onnxruntime.get_available_providers()
        print(f"Providers: {providers}")
        model = onnxruntime.InferenceSession(model_path, providers=providers)

        inputs = model.get_inputs()
        self.shape = inputs[0].shape[1:3]
        self.type = inputs[0].type

        # 3 outputs => multi-task
        outputs = model.get_outputs()
        if len(outputs) > 2:
            self.with_boxes = True
            self.with_masks = True
        # 2 outputs => detection
        elif len(outputs) > 1:
            self.with_boxes = True
            self.with_masks = False
        # 1 outputs => segmentation
        else:
            self.with_boxes = False
            self.with_masks = True

        self.output_names = [x.name for x in outputs]

        return model

    def run_onnx(self, inputs: np.ndarray):
        if "float" in self.type:
            inputs = np.array(inputs, dtype=np.float32)
        else:
            inputs = np.array(inputs, dtype=np.uint8)

        outputs = self.model.run(self.output_names,
                                 {self.model.get_inputs()[0].name: inputs})

        boxes, classes, scores, masks = None, None, None, None
        if isinstance(outputs, list):
            for output in outputs:
                if len(output.shape) == 4:
                    if output.shape[-2] == 1:
                        boxes = output
                    else:
                        masks = output
                else:
                    scores = output
        else:
            masks = outputs

        if boxes is not None and scores is not None:
            boxes, classes, scores = self.nms(
                boxes,
                scores,
                iou_threshold=self.iou_threshold,
                score_threshold=self.score_threshold
            )

        if self.with_boxes and self.with_masks:
            return boxes, classes, scores, masks
        elif self.with_boxes:
            return boxes, classes, scores
        return masks

    @staticmethod
    def input_preprocess(sample: bytes):
        buffer = sample.get_buffer()
        caps = sample.get_caps()
        structure = caps.get_structure(0)

        width = structure.get_value('width')
        height = structure.get_value('height')
        format_str = structure.get_value('format')  # Usually "RGB" or "BGR"

        # Map the buffer and get the raw data
        success, map_info = buffer.map(Gst.MapFlags.READ)
        if not success:
            raise RuntimeError("Failed to map buffer.")

        try:
            data = map_info.data  # raw bytes
            inputs = np.frombuffer(data, dtype=np.uint8)
            if format_str == 'RGB':
                inputs = inputs.reshape((height, width, 3))
            elif format_str == 'BGR':
                inputs = inputs.reshape((height, width, 3))
                inputs = inputs[:, :, ::-1]  # convert BGR to RGB
            else:
                raise ValueError(f"Unsupported format: {format_str}")

            return inputs
        finally:
            buffer.unmap(map_info)

    def nms(
        self,
        bboxes: np.ndarray,
        pscores: np.ndarray,
        iou_threshold: float,
        score_threshold: float
    ):

        # Reshape boxes and scores and compute classes
        bboxes = np.reshape(bboxes, (-1, 4))

        if self.with_masks:  # Multitask
            pscores = pscores[0][..., 1:]  # remove background boxes first
        else:
            pscores = pscores[0]
        classes = np.argmax(pscores, axis=-1).reshape(-1)

        # Prefilter boxes and scores by minimum score
        max_scores = np.max(pscores, axis=-1)
        mask = max_scores >= score_threshold

        # Prefilter the boxes, scores and classes IDs
        pscores = max_scores[mask]
        bboxes = bboxes[mask]
        classes = classes[mask]

        xmin = bboxes[:, 0]
        ymin = bboxes[:, 1]
        xmax = bboxes[:, 2]
        ymax = bboxes[:, 3]

        sorted_idx = pscores.argsort()[::-1]
        areas = (xmax - xmin + 1) * (ymax - ymin + 1)

        keep = []
        while len(sorted_idx) > 0:
            rbbox_i = sorted_idx[0]
            keep.append(rbbox_i)

            overlap_xmins = np.maximum(xmin[rbbox_i], xmin[sorted_idx[1:]])
            overlap_ymins = np.maximum(ymin[rbbox_i], ymin[sorted_idx[1:]])
            overlap_xmaxs = np.minimum(xmax[rbbox_i], xmax[sorted_idx[1:]])
            overlap_ymaxs = np.minimum(ymax[rbbox_i], ymax[sorted_idx[1:]])

            overlap_widths = np.maximum(0, (overlap_xmaxs - overlap_xmins+1))
            overlap_heights = np.maximum(0, (overlap_ymaxs - overlap_ymins+1))
            overlap_areas = overlap_widths * overlap_heights

            ious = overlap_areas / \
                (areas[rbbox_i] + areas[sorted_idx[1:]] - overlap_areas)

            delete_idx = np.where(ious > iou_threshold)[0]+1
            delete_idx = np.concatenate(([0], delete_idx))

            sorted_idx = np.delete(sorted_idx, delete_idx)

        # Filter boxes, scores, and classes
        boxes = bboxes[keep]
        scores = pscores[keep]
        classes = classes[keep]

        return boxes, classes, scores

    @staticmethod
    def softmax(x: np.ndarray):
        # Subtract the maximum for numerical stability
        e_x = np.exp(x - np.max(x, axis=-1, keepdims=True))
        return e_x / np.sum(e_x, axis=-1, keepdims=True)


def login(
    username: str, 
    password: str, 
    server: str, 
    session_id: str, 
    model_path: str, 
    labels_path: str
):
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

    client.download_artifact_sync(
        session_id, model_path, filename=os.path.basename(model_path))
    client.download_artifact_sync(
        session_id, labels_path, filename=os.path.basename(labels_path))


def on_new_sample(app_sink, ctx):
    sample = app_sink.pull_sample()
    frame = ctx.input_preprocess(sample)
    h, w = frame.shape[:2]
    outputs = ctx.run_model(frame)

    boxes, classes, scores = [], [], []
    masks = None
    if ctx.with_boxes and ctx.with_masks:
        boxes, classes, scores, masks = outputs
        boxes = boxes * [w, h, w, h]
    elif ctx.with_boxes:
        boxes, classes, scores = outputs
        boxes = boxes * [w, h, w, h]
    else:
        masks = outputs

    # Start a new frame log
    rr.set_time("camera", sequence=ctx.frame_id)
    rr.log("camera", rr.Image(frame).compress(jpeg_quality=90))

    ctx_labels = ctx.labels
    if ctx_labels is not None and "background" in ctx_labels:
        ctx_labels.remove("background")

    labels = []
    for i, box in enumerate(boxes):
        print('    %s [%3d%%]: %3.2f %3.2f %3.2f %3.2f' % (
            ctx_labels[int(classes[i])] if ctx_labels else int(classes[i]),
            scores[i] * 100,
            box[0],
            box[1],
            box[2],
            box[3]))

        labels.append("%s, [%3d%%]" % (
            ctx_labels[int(classes[i])] if ctx_labels else int(classes[i]),
            scores[i] * 100)
        )

    if masks is not None:
        nc = masks.shape[0]
        resized_mask = np.zeros((nc, h, w), dtype=np.uint8)
        masks = ctx.softmax(masks)
        masks = np.argmax(masks, axis=-1).astype(np.uint8)
        print(f"Mask Labels: {np.unique(masks)}")

        for i, mask in enumerate(masks):
            mask = Image.fromarray(mask)
            mask = mask.resize((w, h), resample=Image.NEAREST)
            mask = np.asarray(mask)
            resized_mask[i] = mask

        rr.log(
            "camera/mask",
            rr.SegmentationImage(resized_mask)
        )

    rr.log(
        "camera/boxes",
        rr.Boxes2D(array=boxes,
                   array_format=rr.Box2DFormat.XYXY,
                   class_ids=classes, labels=labels)
    )
    ctx.frame_id += 1

    return False


def on_error(bus, msg, loop, pipeline):
    err, dbg = msg.parse_error()
    print(err.message)
    pipeline.set_state(Gst.State.NULL)  # <---- ADD THIS LINE
    loop.quit()


def main():
    args = ArgumentParser(description="EdgeFirst Samples - Deploying Modelpack",
                          formatter_class=RawTextHelpFormatter)
    args.add_argument('-u', '--user'
                      'name', type=str, default=None,
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
    args.add_argument('-c', '--camera', type=str, default="/dev/video3",
                      help="Specify the video4linux2 camera device for capture.")
    args.add_argument('-r', '--resolution', type=str, default='640x480',
                      help='Specify the camera capture resolution.')
    args.add_argument('-m', '--model', type=str, required=True,
                      help=("Specify the path to the model or the model to download. "
                            "Examples include modelpack.tflite, modelpack.onnx"))
    args.add_argument('-l', '--labels', type=str, default='labels.txt',
                      help=("Specify the path to the labels.txt to map label "
                            "indices to string."))
    args.add_argument('-d', '--delegate', type=str, default='/usr/lib/libvx_delegate.so',
                      help="Specify the path to the NPU delegate for the TFLite.")
    args.add_argument('--rerun', type=str, default='modelpack-sample.rrd',
                      help="Specify the path to save the rerun file.")
    args.add_argument('--score-threshold', type=float, default=0.25,
                      help="NMS score threshold.")
    args.add_argument('--iou-threshold', type=float, default=0.50,
                      help="NMS IoU threshold.")
    args = args.parse_args()

    model_path = args.model
    if model_path and not os.path.exists(model_path):
        print(
            f"Warning: The model {model_path} does not exist. Attempting to download...")

        if None in [args.username, args.password]:
            raise ValueError(
                "Please specify your EdgeFirst Studio username and password.")

        if args.trainer is None:
            raise ValueError(
                "Please specify the training session ID to fetch artifacts.")

        login(args.username, args.password,
              args.server, args.trainer, model_path, args.labels)

    ctx = Model(score_threshold=args.score_threshold,
                iou_threshold=args.iou_threshold)
    ctx.load_model(model_path=model_path, delegate=args.delegate)
    ctx.load_labels(labels_path=args.labels)

    rr.init("ModelPack", spawn=False)
    rr.save(args.rerun)
    ctx.frame_id = 0

    # This is needed to expose the app_sink.pull_sample() function.
    _ = GstApp
    Gst.init(None)

    camera_width, camera_height = map(int, args.resolution.split('x'))
    print('capturing from %s at %dx%d' %
          (args.camera, camera_width, camera_height))

    loop = GLib.MainLoop()
    pipeline = Gst.parse_launch("""
        v4l2src device=%s !
        video/x-raw,format=RGB,width=%d,height=%d !
        queue !
        appsink sync=true max-buffers=1 drop=true name=sink emit-signals=true
    """ % (args.camera, camera_width, camera_height))
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message::error", on_error, loop, pipeline)
    appsink = pipeline.get_by_name("sink")
    appsink.connect("new-sample", on_new_sample, ctx)
    pipeline.set_state(Gst.State.PLAYING)
    loop.run()


if __name__ == '__main__':
    """
    If the model needs to be downloaded from EdgeFirst Studio, run the command.

    ```
    python3 python/model/modelpack.py \
        --model modelpack.tflite \
        --server <server> \
        --username <username> \
        --password <password> \
        --trainer <trainer session ID>
    ```

    Otherwise, if the model artifacts is already downloaded, run the command.

    ```
    python3 python/model/modelpack.py \
        --model <path to the TFLite or ONNX model> \
        --labels <path to the labels.txt>
    ```
    """
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
