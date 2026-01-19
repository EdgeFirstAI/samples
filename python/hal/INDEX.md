# EdgeFirst HAL Library - Complete Documentation Index

## Overview

Comprehensive documentation and working examples for the `edgefirst_hal` library - a hardware abstraction layer for optimized image processing and ML inference on edge devices.

**Location:** `python/hal/`

## Documentation Files

### 1. [QUICKSTART.md](QUICKSTART.md) ⚡ **Start Here**
- **For:** Developers new to HAL
- **Content:** 5-minute overview, common patterns, minimal examples
- **Key Sections:**
  - What is edgefirst_hal in simple terms
  - Minimal working example
  - 4 common patterns with code
  - Installation and testing
  - Troubleshooting table

**Read this first if you're just getting started.**

### 2. [EDGEFIRST_HAL_GUIDE.md](EDGEFIRST_HAL_GUIDE.md) 📚 **Complete API Reference**
- **For:** Developers implementing HAL-based applications
- **Content:** Comprehensive API documentation for all components
- **Key Sections:**
  - TensorImage class (constructor, methods, examples)
  - ImageConverter class (usage patterns)
  - Decoder class (YOLO decoding)
  - FourCC pixel formats reference
  - Performance considerations
  - Integration with ONNX Runtime
  - Integration with EdgeFirst schemas
  - Troubleshooting guide

**Reference this when building HAL applications.**

### 3. [DEVELOPMENT_SUMMARY.md](DEVELOPMENT_SUMMARY.md) 🎯 **Strategic Overview**
- **For:** Project leads, architects, experienced developers
- **Content:** Deep analysis and development opportunities
- **Key Sections:**
  - Executive summary
  - Understanding edgefirst_hal (comprehensive breakdown)
  - New tracking sample design
  - Documentation overview
  - Further development opportunities
  - Performance characteristics
  - Best practices
  - Conclusion

**Reference when planning new features or tracking variants.**

### 4. [README.md](README.md) 📖 **Sample Gallery & Practical Guide**
- **For:** Developers using or learning from examples
- **Content:** Overview of all three samples with patterns
- **Key Sections:**
  - Overview of HAL capabilities
  - Three samples described (resize.py, decoder.py, tracking.py)
  - Key patterns for each sample with code
  - HAL library reference
  - Performance tips
  - Common patterns
  - Integration notes (Zenoh, Rerun, ONNX)
  - Dependencies
  - Troubleshooting

**Reference when working with actual samples.**

## Code Examples

### [resize.py](resize.py) - Basic Image Operations
**Complexity:** ⭐ Beginner  
**Purpose:** Demonstrate simple image resizing and JPEG export

```python
import edgefirst_hal as ef

ef_im = ef.TensorImage(width, height, ef.FourCC.RGB)
ef_im.copy_from_numpy(frame_array)
converter = ef.ImageConverter()
output = ef.TensorImage(640, 640)
converter.convert(ef_im, output)
ef_im.save_jpeg('output.jpg')
```

**Learn:** Basic TensorImage usage, ImageConverter basics

### [decoder.py](decoder.py) - YOLO Detection
**Complexity:** ⭐⭐ Intermediate  
**Purpose:** Full detection pipeline with H.264 decoding and YOLO inference

Features:
- H.264 video decoding (PyAV)
- HAL preprocessing (TensorImage + ImageConverter)
- ONNX Runtime inference
- HAL Decoder for YOLO output
- Basic object tracking
- Zenoh integration

**Learn:** Full inference pipeline, HAL decoder usage, tracking basics

### [tracking.py](tracking.py) - Real-Time Tracking ⭐ **New**
**Complexity:** ⭐⭐⭐ Advanced  
**Purpose:** Production-ready object tracking with persistent IDs

Features:
- H.264 video stream processing
- Hardware-accelerated preprocessing
- YOLO object detection
- **Centroid-based object tracking** (new)
- Persistent track IDs across frames
- Automatic track creation/cleanup
- Rerun visualization
- Configurable tracking parameters
- Error handling and logging

**Learn:** Advanced tracking, state management, production patterns

**Key Classes:**
- `TrackState` - Individual track representation
- `SimpleTracker` - Centroid-based tracking engine
- `FrameSize` - Async coordination
- `MessageDrain` - Async Zenoh integration

## Quick Navigation

### By Use Case

**I want to...** → **Read this**

| Goal | Document | File |
|------|----------|------|
| Understand HAL basics | QUICKSTART.md | - |
| Build a simple resize app | EDGEFIRST_HAL_GUIDE.md | resize.py |
| Run YOLO inference | README.md | decoder.py |
| Implement object tracking | DEVELOPMENT_SUMMARY.md | tracking.py |
| Deep dive into HAL | EDGEFIRST_HAL_GUIDE.md | - |
| Optimize performance | DEVELOPMENT_SUMMARY.md | tracking.py |
| Extend tracking further | DEVELOPMENT_SUMMARY.md | tracking.py |

### By Learning Path

**Beginner:**
1. QUICKSTART.md (5 min)
2. Run resize.py
3. README.md (overview section)

**Intermediate:**
1. README.md (full)
2. Run decoder.py
3. EDGEFIRST_HAL_GUIDE.md (reference as needed)

**Advanced:**
1. DEVELOPMENT_SUMMARY.md
2. Analyze tracking.py source
3. Plan custom tracking variant
4. EDGEFIRST_HAL_GUIDE.md (deep API reference)

### By Component

**TensorImage:**
- QUICKSTART.md - Pattern 1
- EDGEFIRST_HAL_GUIDE.md - Core Components → TensorImage Class
- README.md - Pattern 1

**ImageConverter:**
- QUICKSTART.md - Pattern 1
- EDGEFIRST_HAL_GUIDE.md - Core Components → ImageConverter Class
- tracking.py - lines ~250

**Decoder (YOLO):**
- QUICKSTART.md - Pattern 3
- EDGEFIRST_HAL_GUIDE.md - Core Components → Decoder Class
- decoder.py - lines ~85
- tracking.py - lines ~290

## File Structure

```
python/hal/
├── QUICKSTART.md              # ⭐ START HERE
├── EDGEFIRST_HAL_GUIDE.md    # API Reference
├── DEVELOPMENT_SUMMARY.md    # Strategy & Future
├── README.md                  # Sample Guide
│
├── resize.py                  # Simple resize example
├── decoder.py                 # YOLO inference example
├── tracking.py                # Tracking example (NEW)
│
├── yolov8n.onnx              # Example model
└── yolov8n.pt                # Original PyTorch model
```

## Key Concepts

### TensorImage
Container for image data with format awareness and NumPy interoperability.
```
NumPy Array → copy_from_numpy() → TensorImage → ImageConverter → TensorImage → normalize_to_numpy() → NumPy Array
```

### ImageConverter
Hardware-accelerated transformation between image formats and resolutions.
```
Input: Any format/resolution
    ↓ (hardware acceleration)
Output: Any format/resolution
```

### Decoder
YOLO-specific post-processing: boxes → NMS → clean detections
```
YOLO Output (25200×85) → decode_yolo_det() → [(box, score, class), ...]
```

### Tracking (NEW)
Centroid-based association maintaining object identities across frames.
```
Detections (t) → Distance Matching → Existing Tracks
                    ↓
            Create/Update/Delete Tracks
                    ↓
            Output: Tracked Objects with IDs
```

## API Quick Reference

### TensorImage Methods
```python
ef.TensorImage(width, height, format=FourCC.RGB)
  .copy_from_numpy(array)
  .normalize_to_numpy(output_array)
  .save_jpeg(filename)
```

### ImageConverter Methods
```python
ef.ImageConverter()
  .convert(input_image, output_image)
```

### Decoder Methods
```python
ef.Decoder.decode_yolo_det(
    predictions,
    anchors=(0.0040811873, -123),
    confidence_threshold=0.25,
    nms_threshold=0.7,
    max_boxes=50,
)
```

### FourCC Formats
```python
ef.FourCC.RGB      # Red-Green-Blue
ef.FourCC.BGR      # Blue-Green-Red
ef.FourCC.GRAY     # Grayscale
ef.FourCC.NV12     # YUV 4:2:0 (hardware cameras)
ef.FourCC.YUYV     # YUV 4:2:2
```

## Running Examples

### Minimal Test
```python
# Verify HAL is installed
python -c "import edgefirst_hal as ef; print('OK')"
```

### Simple Resize
```bash
python python/hal/resize.py --remote 192.168.1.100:7447
```

### YOLO Inference
```bash
python python/hal/decoder.py -m python/hal/yolov8n.onnx --remote 192.168.1.100:7447
```

### Tracking with Visualization
```bash
python python/hal/tracking.py -m python/hal/yolov8n.onnx --remote 192.168.1.100:7447
```

### Headless Tracking (Production)
```bash
python python/hal/tracking.py -m python/hal/yolov8n.onnx --remote 192.168.1.100:7447 --no-visualization
```

## Performance Notes

| Operation | Time | Memory |
|-----------|------|--------|
| H.264 decode | ~5ms | 10-20MB |
| HAL preprocessing | ~2ms | <5MB |
| YOLO inference | ~10-30ms | 50-100MB |
| Centroid tracking | <1ms | <1MB |
| Rerun visualization | ~2-5ms | 50-100MB |
| **Total per frame** | **~20-50ms** | **~200-500MB** |

## Common Issues & Solutions

### ImportError: No module named 'edgefirst_hal'
→ Install: `pip install edgefirst-hal`

### ValueError: Shape mismatch
→ Remember: NumPy is (height, width, channels), TensorImage is (width, height)

### Poor tracking results
→ Adjust MAX_DISTANCE threshold (try 0.05 to 0.2)

### Memory issues
→ Disable visualization or reduce queue size

See EDGEFIRST_HAL_GUIDE.md Troubleshooting section for more.

## Next Steps

1. **Read:** QUICKSTART.md (5 minutes)
2. **Run:** `python python/hal/resize.py` 
3. **Explore:** Look at tracking.py source code
4. **Reference:** EDGEFIRST_HAL_GUIDE.md when needed
5. **Extend:** Follow patterns to build custom applications

## Support & References

- **EdgeFirst Documentation:** https://doc.edgefirst.ai/
- **YOLO Format:** https://docs.ultralytics.com/
- **ONNX Runtime:** https://onnxruntime.ai/
- **Zenoh:** https://zenoh.io/

## Document Versions

| Document | Last Updated | Version |
|----------|--------------|---------|
| QUICKSTART.md | January 2026 | 1.0 |
| EDGEFIRST_HAL_GUIDE.md | January 2026 | 1.0 |
| DEVELOPMENT_SUMMARY.md | January 2026 | 1.0 |
| README.md | January 2026 | 1.0 |
| tracking.py | January 2026 | 1.0 |

---

**Created:** January 2026  
**Organization:** Au-Zone Technologies  
**License:** Apache 2.0
