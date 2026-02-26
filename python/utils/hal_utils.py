
import edgefirst_hal as ef


CONVERTER = ef.ImageProcessor()

def hal_letterbox(image: ef.TensorImage, dst: ef.TensorImage,
                  constant: int = 114):
    ratio = min(dst.height / image.height, dst.width / image.width)
    height = image.height * ratio
    width = image.width * ratio
    top = round((dst.height - height) / 2)
    left = round((dst.width - width) / 2)
    height = round(height)
    width = round(width)
    CONVERTER.convert(image, dst,
                      dst_crop=ef.Rect(left, top, width, height),
                      dst_color=[constant, constant, constant, 255])
                      