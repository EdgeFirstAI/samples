FROM deepview/rust AS base

# Prevent tzdata prompts
ENV DEBIAN_FRONTEND=noninteractive

# Enable ARM64 architecture
RUN dpkg --add-architecture arm64

# Add LLVM repository
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    lsb-release \
    software-properties-common \
    && wget -O - https://apt.llvm.org/llvm-snapshot.gpg.key | apt-key add - \
    && echo "deb http://apt.llvm.org/$(lsb_release -cs)/ llvm-toolchain-$(lsb_release -cs)-14 main" > /etc/apt/sources.list.d/llvm.list

# Update & install all required packages in one go
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    cmake \
    ninja-build \
    llvm-14 \
    clang-14 \
    lld-14 \
    libclang-14-dev \
    pkg-config \
    yasm \
    nasm \
    python3 \
    python3-pip \
    crossbuild-essential-arm64 \
    gcc-aarch64-linux-gnu \
    g++-aarch64-linux-gnu \
    libssl-dev \
    libssl-dev:arm64 \
    libavcodec-dev:arm64 \
    libavformat-dev:arm64 \
    libavutil-dev:arm64 \
    libswscale-dev:arm64 \
    libswresample-dev:arm64 \
    libavfilter-dev:arm64 \
    libavdevice-dev:arm64 \
    && rm -rf /var/lib/apt/lists/*

# Add Rust target for ARM64
RUN rustup target add aarch64-unknown-linux-gnu

# Set environment variables for cross-compilation
ENV CARGO_TARGET_AARCH64_UNKNOWN_LINUX_GNU_LINKER=aarch64-linux-gnu-gcc \
    AR_aarch64_unknown_linux_gnu=aarch64-linux-gnu-ar \
    CC_aarch64_unknown_linux_gnu=aarch64-linux-gnu-gcc \
    CXX_aarch64_unknown_linux_gnu=aarch64-linux-gnu-g++ \
    PKG_CONFIG_ALLOW_CROSS=1 \
    PKG_CONFIG_PATH=/usr/lib/aarch64-linux-gnu/pkgconfig \
    PKG_CONFIG_SYSROOT_DIR=/usr/aarch64-linux-gnu \
    LIBCLANG_PATH=/usr/lib/llvm-14/lib \
    CFLAGS="-I/usr/include/aarch64-linux-gnu -I/usr/include" \
    CXXFLAGS="-I/usr/include/aarch64-linux-gnu -I/usr/include" \
    LDFLAGS="-L/usr/lib/aarch64-linux-gnu"

# Create necessary directories and symlinks for FFmpeg headers
RUN mkdir -p /usr/include && \
    ln -s /usr/include/aarch64-linux-gnu/libav* /usr/include/ && \
    ln -s /usr/include/aarch64-linux-gnu/libsw* /usr/include/ && \
    ln -s /usr/include/aarch64-linux-gnu/ffmpeg* /usr/include/

# Create pkg-config files for FFmpeg libraries
RUN mkdir -p /usr/lib/aarch64-linux-gnu/pkgconfig && \
    for lib in avcodec avformat avutil swscale avfilter swresample avdevice; do \
        echo "prefix=/usr" > /usr/lib/aarch64-linux-gnu/pkgconfig/lib${lib}.pc && \
        echo "exec_prefix=\${prefix}" >> /usr/lib/aarch64-linux-gnu/pkgconfig/lib${lib}.pc && \
        echo "libdir=\${exec_prefix}/lib/aarch64-linux-gnu" >> /usr/lib/aarch64-linux-gnu/pkgconfig/lib${lib}.pc && \
        echo "includedir=\${prefix}/include" >> /usr/lib/aarch64-linux-gnu/pkgconfig/lib${lib}.pc && \
        echo "" >> /usr/lib/aarch64-linux-gnu/pkgconfig/lib${lib}.pc && \
        echo "Name: lib${lib}" >> /usr/lib/aarch64-linux-gnu/pkgconfig/lib${lib}.pc && \
        echo "Description: FFmpeg ${lib} library" >> /usr/lib/aarch64-linux-gnu/pkgconfig/lib${lib}.pc && \
        echo "Version: 58.134.100" >> /usr/lib/aarch64-linux-gnu/pkgconfig/lib${lib}.pc && \
        echo "Requires: libavutil >= 56.70.100" >> /usr/lib/aarch64-linux-gnu/pkgconfig/lib${lib}.pc && \
        echo "Requires.private:" >> /usr/lib/aarch64-linux-gnu/pkgconfig/lib${lib}.pc && \
        echo "Conflicts:" >> /usr/lib/aarch64-linux-gnu/pkgconfig/lib${lib}.pc && \
        echo "Libs: -L\${libdir} -l${lib}" >> /usr/lib/aarch64-linux-gnu/pkgconfig/lib${lib}.pc && \
        echo "Libs.private: -lm" >> /usr/lib/aarch64-linux-gnu/pkgconfig/lib${lib}.pc && \
        echo "Cflags: -I\${includedir}" >> /usr/lib/aarch64-linux-gnu/pkgconfig/lib${lib}.pc; \
    done

# Optional: Download static FFmpeg binaries for ARM64 if using subprocess
RUN mkdir -p /usr/aarch64-linux-gnu/bin && \
    curl -L https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-arm64-static.tar.xz | \
    tar -xJ --strip-components=1 -C /usr/aarch64-linux-gnu/bin

# Make ffmpeg/ffprobe globally available (optional)
RUN ln -s /usr/aarch64-linux-gnu/bin/ffmpeg /usr/local/bin/ffmpeg && \
    ln -s /usr/aarch64-linux-gnu/bin/ffprobe /usr/local/bin/ffprobe

# Verify installations
RUN echo "Checking FFmpeg headers:" && \
    ls -la /usr/include/libswscale/swscale.h && \
    echo "Checking libclang:" && \
    ls -la /usr/lib/llvm-14/lib/libclang* && \
    echo "LIBCLANG_PATH is set to: $LIBCLANG_PATH"

# Set working directory
WORKDIR /app

# Copy your project files (adjust as needed)
COPY . .

# Optional: build for ARM64
# RUN cargo build --release --target aarch64-unknown-linux-gnu

# Default command (optional)
CMD ["bash"]
