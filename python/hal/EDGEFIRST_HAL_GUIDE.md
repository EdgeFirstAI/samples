# EdgeFirst HAL Library Guide

## Overview

The `edgefirst_hal` library provides hardware abstraction for image processing and inference on EdgeFirst platforms. It offers optimized image conversion, resizing, and ML model decoding capabilities designed for resource-constrained edge devices.

## Core Components

### 1. TensorImage Class

Represents an image tensor with support for multiple pixel formats and operations.

#### Constructor
```python
ef.TensorImage(width, height, format=FourCC.RGB)
```

**Parameters:**
- `width`: Image width in pixels
- `height`: Image height in pixels
- `format`: Pixel format (default: RGB). Options include:
  - `ef.FourCC.RGB` - RGB color space
  - `ef.FourCC.BGR` - BGR color space  
  - `ef.FourCC.GRAY` - Grayscale
  - Other standard video formats

#### Key Methods

**`copy_from_numpy(array)`**
- Copies data from NumPy array into TensorImage
- Input array should match the image format and dimensions

**`normalize_to_numpy(output_array)`**
- Normalizes and copies TensorImage data to NumPy array
- Handles format conversion and value scaling
- Common usage: Convert model output (0-1 float) to display (0-255 uint8)

**`save_jpeg(filename)`**
- Saves image as JPEG file
- Useful for debugging and testing

#### Example Usage
```python
# Create RGB image from H.264 frame
frame_array = frame.to_ndarray(format="rgb24")  # NumPy array from PyAV
ef_im = ef.TensorImage(frame_array.shape[1], frame_array.shape[0], ef.FourCC.RGB)
ef_im.copy_from_numpy(frame_array)

# Save for debugging
ef_im.save_jpeg('debug_frame.jpg')
```

### 2. ImageConverter Class

Handles image format conversion and resizing operations with hardware acceleration where available.

#### Constructor
```python
converter = ef.ImageConverter()
```

#### Key Methods

**`convert(input_image, output_image)`**
- Converts between different formats, resolutions, or color spaces
- Performs optimized resizing if input and output have different dimensions
- Handles format conversion (RGB↔BGR, color↔grayscale, etc.)

#### Example Usage
```python
# Resize and convert RGB 1080p to 640x640 for YOLO inference
input_im = ef.TensorImage(1920, 1080, ef.FourCC.RGB)
input_im.copy_from_numpy(frame_array)

output_im = ef.TensorImage(640, 640)  # Default to RGB
converter = ef.ImageConverter()
converter.convert(input_im, output_im)

# Extract to NumPy for model inference
out_array = np.zeros((640, 640, 3), dtype=np.uint8)
output_im.normalize_to_numpy(out_array)
```

### 3. Decoder Class

Provides specialized decoding functions for ML model outputs, particularly vision models.

#### Static Methods

**`Decoder.decode_yolo_det(predictions, anchors, confidence_threshold, nms_threshold, max_boxes)`**
- Decodes YOLO detection output into structured bounding boxes
- Performs NMS (Non-Maximum Suppression) filtering

**Parameters:**
- `predictions`: Model output tensor (squeezed)
- `anchors`: Tuple of (scale, offset) for anchor boxes
- `confidence_threshold`: Minimum confidence for detection (0.0-1.0)
- `nms_threshold`: NMS IoU threshold (0.0-1.0)
- `max_boxes`: Maximum number of boxes to return

**Returns:**
- `boxes`: List of bounding box coordinates [x1, y1, x2, y2]
- `scores`: List of confidence scores
- `classes`: List of class indices

#### Example Usage
```python
# After YOLO inference
predictions = ort_session.run(None, {input_name: input_tensor})[0]

boxes, scores, classes = ef.Decoder.decode_yolo_det(
    predictions.squeeze(),
    anchors=(0.0040811873, -123),  # YOLO-specific anchors
    confidence_threshold=0.25,
    nms_threshold=0.7,
    max_boxes=50,
)

for box, score, cls_idx in zip(boxes, scores, classes):
    print(f"Class: {cls_idx}, Confidence: {score:.2f}, Box: {box}")
```

## FourCC Pixel Formats

Standard pixel format enumeration:

```python
ef.FourCC.RGB    # Red-Green-Blue
ef.FourCC.BGR    # Blue-Green-Red
ef.FourCC.GRAY   # Grayscale
ef.FourCC.NV12   # YUV 4:2:0 planar (common in hardware)
ef.FourCC.YUYV   # YUV 4:2:2 interleaved
```

## Performance Considerations

### Memory Efficiency
- `TensorImage` objects manage memory efficiently
- Reuse converter instances when possible (create once, use many times)
- Pre-allocate output arrays for `normalize_to_numpy()`

### Hardware Acceleration
- Conversion operations leverage NPU/GPU when available
- Anchor-based decoding (YOLO) is optimized for edge inference
- Use appropriate confidence thresholds to reduce post-processing overhead

### Common Workflow Patterns

**Pattern 1: Simple Image Resize**
```python
# 1080p input → 640x640 for inference
input_im = ef.TensorImage(1920, 1080, ef.FourCC.RGB)
input_im.copy_from_numpy(frame_data)

output_im = ef.TensorImage(640, 640)
converter = ef.ImageConverter()
converter.convert(input_im, output_im)

# Extract and prepare for model
inference_input = np.zeros((640, 640, 3), dtype=np.uint8)
output_im.normalize_to_numpy(inference_input)
```

**Pattern 2: Format Conversion**
```python
# BGR → RGB conversion
bgr_im = ef.TensorImage(640, 480, ef.FourCC.BGR)
bgr_im.copy_from_numpy(bgr_data)

rgb_im = ef.TensorImage(640, 480, ef.FourCC.RGB)
converter.convert(bgr_im, rgb_im)
```

**Pattern 3: YUV → RGB (hardware camera)**
```python
# YUV 4:2:0 from camera → RGB for processing
yuv_im = ef.TensorImage(1920, 1080, ef.FourCC.NV12)
yuv_im.copy_from_numpy(raw_camera_data)

rgb_im = ef.TensorImage(640, 640, ef.FourCC.RGB)
converter.convert(yuv_im, rgb_im)
```

## Integration with Other EdgeFirst Components

### With ONNX Runtime
```python
import onnxruntime as ort
import edgefirst_hal as ef

# Load model
ort_session = ort.InferenceSession("model.onnx")

# Prepare input using HAL
ef_im = ef.TensorImage(1920, 1080, ef.FourCC.RGB)
ef_im.copy_from_numpy(frame_data)

output_im = ef.TensorImage(640, 640)
converter = ef.ImageConverter()
converter.convert(ef_im, output_im)

# Convert to model input format
input_array = np.zeros((640, 640, 3), dtype=np.uint8)
output_im.normalize_to_numpy(input_array)
input_tensor = input_array.astype(np.float32) / 255.0

# Run inference
outputs = ort_session.run(None, {input_name: input_tensor})
```

### With EdgeFirst Schemas
```python
from edgefirst.schemas.edgefirst_msgs import Detect

# Decoder produces results compatible with EdgeFirst message types
boxes, scores, classes = ef.Decoder.decode_yolo_det(...)

# Can be packaged into Detect messages for publication
for box, score, cls in zip(boxes, scores, classes):
    # Create detection message
    pass
```

## Troubleshooting

### Issue: AttributeError on ef.FourCC
**Cause:** FourCC enum not directly imported  
**Solution:** Ensure using `ef.FourCC.RGB` not just `FourCC.RGB`

### Issue: Dimension mismatch in normalize_to_numpy
**Cause:** Output array shape doesn't match TensorImage dimensions  
**Solution:** Allocate array as `(height, width, channels)` for RGB

### Issue: Poor inference results after conversion
**Cause:** Improper normalization or format conversion  
**Solution:** 
- Verify input format matches model expectations
- Check normalize_to_numpy produces correct value range
- Test with reference images

## Example Applications

See `decoder.py` and `resize.py` in `python/hal/` for working examples:

- **decoder.py**: H.264 decoding + YOLO inference + object tracking
- **resize.py**: Simple image resizing with JPEG output

## References

- EdgeFirst Perception Middleware Documentation
- YOLO Model Format Specification
- HAL Hardware Acceleration Guide (internal)
