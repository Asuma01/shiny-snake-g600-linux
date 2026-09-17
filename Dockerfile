FROM ubuntu:22.04 AS ffmpeg_builder
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates curl gnupg xz-utils zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp/ffmpeg-source
RUN curl -fsSLO https://ffmpeg.org/releases/ffmpeg-9.0.1.tar.xz \
    && curl -fsSLO https://ffmpeg.org/releases/ffmpeg-9.0.1.tar.xz.asc \
    && curl -fsSLO https://ffmpeg.org/ffmpeg-devel.asc \
    && gpg --batch --import ffmpeg-devel.asc \
    && gpg --batch --status-fd 1 --verify \
        ffmpeg-9.0.1.tar.xz.asc ffmpeg-9.0.1.tar.xz \
        | grep -q 'VALIDSIG FCF986EA15E6E293A5644F10B4322F04D67658D8' \
    && tar -xf ffmpeg-9.0.1.tar.xz

WORKDIR /tmp/ffmpeg-source/ffmpeg-9.0.1
RUN ./configure \
        --disable-gpl --disable-nonfree --disable-autodetect \
        --disable-doc --disable-debug --disable-ffplay --disable-ffprobe \
        --disable-x86asm --disable-network \
        --enable-zlib --enable-static --disable-shared --extra-ldflags=-static \
    && make -j2 ffmpeg \
    && strip ffmpeg \
    && install -m 755 ffmpeg /tmp/ffmpeg

FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    binutils ca-certificates libpython3.10 python3 python3-pip python3-tk python3-venv \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/g600-build \
    && /opt/g600-build/bin/pip install --no-cache-dir \
        'pyinstaller==6.22.3' 'pyserial==3.5' 'dbus-next==0.2.3'

COPY --from=ffmpeg_builder /tmp/ffmpeg /tmp/ffmpeg
COPY --from=ffmpeg_builder /tmp/ffmpeg-source/ffmpeg-9.0.1.tar.xz /tmp/ffmpeg-9.0.1.tar.xz
COPY . /src
WORKDIR /src
RUN PATH="/opt/g600-build/bin:$PATH" FFMPEG_BIN=/tmp/ffmpeg ./build-onefile.sh \
    && cp /tmp/ffmpeg-9.0.1.tar.xz dist/
