# The music image: where Groundhold's music, ambience and sampled cues are rendered (art_src/music/).
#
# It holds the free libraries palette.py names, fetched here at pinned commits and never committed to git (each
# one's licence lets us ship audio rendered from it: palette.py's LIBRARIES), the two renderers (sfizz for SFZ,
# FluidSynth for SF2) and Python with NumPy, SciPy and Pillow for the mix, the check and the pictures, and ffmpeg
# for OGG and spectrograms. Built by art_src/music/render.py when missing, as groundhold-music:
#
#     docker build -t groundhold-music art_src/music
#
# Rebuild it after palette.py changes (its sparse patterns pick the files fetched).

# sfizz's command-line renderer, patched to write 32-bit float WAV: the stock one writes 16-bit and clips at full
# scale, and a part rendered alone must keep its headroom for the mix.
FROM debian:trixie AS sfizz
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential cmake ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*
ARG SFIZZ_URL=https://github.com/sfztools/sfizz/releases/download/1.2.3/sfizz-1.2.3.tar.gz
ARG SFIZZ_SHA256=a9339eac7620d7f0f6b44bdfe860680fab73e66efad4b5f15b21198dd9436822
WORKDIR /build
RUN curl -fsSL -o sfizz.tar.gz "$SFIZZ_URL" \
 && echo "$SFIZZ_SHA256  sfizz.tar.gz" | sha256sum -c - \
 && tar xzf sfizz.tar.gz && rm sfizz.tar.gz
WORKDIR /build/sfizz-1.2.3
RUN sed -i \
      -e 's/outputFormat.format = DR_WAVE_FORMAT_PCM;/outputFormat.format = DR_WAVE_FORMAT_IEEE_FLOAT;/' \
      -e 's/outputFormat.bitsPerSample = 16;/outputFormat.bitsPerSample = 32;/' \
      -e '/drwav_f32_to_s16(interleavedPcm.data(), interleavedBuffer.data(), 2 \* blockSize);/d' \
      -e 's/drwav_write_pcm_frames(&outputFile, blockSize, interleavedPcm.data())/drwav_write_pcm_frames(\&outputFile, blockSize, interleavedBuffer.data())/' \
      clients/sfizz_render.cpp \
 && grep -q 'DR_WAVE_FORMAT_IEEE_FLOAT' clients/sfizz_render.cpp \
 && ! grep -q 'drwav_f32_to_s16' clients/sfizz_render.cpp \
 && cmake -B out -DCMAKE_BUILD_TYPE=Release -DSFIZZ_JACK=OFF -DSFIZZ_RENDER=ON -DSFIZZ_SHARED=OFF \
      -DENABLE_LTO=OFF -DSFIZZ_GIT_SUBMODULE_CHECK=OFF -DSFIZZ_TESTS=OFF \
 && cmake --build out --target sfizz_render -j"$(nproc)" \
 && cp "$(find out -name sfizz_render -type f -perm -u+x | head -1)" /usr/local/bin/sfizz_render

# The libraries: a sparse, blob-less fetch of each at its pinned commit, keeping only what palette.py names.
FROM debian:trixie AS sounds
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends git ca-certificates python3 \
 && rm -rf /var/lib/apt/lists/*
COPY palette.py /palette.py
RUN set -e; fetch() { \
      lib="$1"; url="$2"; commit="$(python3 -c "import sys; sys.path.insert(0, '/'); import palette; print(palette.LIBRARIES['$1']['commit'])")"; \
      mkdir -p "/opt/sounds/$lib" && cd "/opt/sounds/$lib"; \
      git init -q . && git remote add origin "$url"; \
      git config core.sparseCheckout true; \
      python3 /palette.py --patterns "$lib" > .git/info/sparse-checkout; \
      git fetch -q --depth 1 --filter=blob:none origin "$commit"; \
      git checkout -q FETCH_HEAD; \
      test "$(git rev-parse HEAD)" = "$commit"; \
      cp .git/info/sparse-checkout /opt/sounds/$lib.patterns; \
      rm -rf .git; \
    }; \
    fetch vsco https://github.com/sgossner/VSCO-2-CE.git; \
    fetch vcsl https://github.com/sgossner/VCSL.git; \
    du -sh /opt/sounds/*

FROM debian:trixie
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    python3 python3-numpy python3-scipy python3-pil fluidsynth fluid-soundfont-gm ffmpeg fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*
COPY --from=sfizz /usr/local/bin/sfizz_render /usr/local/bin/sfizz_render
COPY --from=sounds /opt/sounds /opt/sounds
ENV GROUNDHOLD_SOUNDS=/opt/sounds
