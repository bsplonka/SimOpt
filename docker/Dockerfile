# MuJoCo, biorbd/bioviz and bioptim with a browser-based display (noVNC).
# Builds and runs natively on arm64 and x86_64, on macOS, Linux and Windows
# hosts.

# Wheels for biorbd, biorbd_casadi, ezc3d, bioviz and bioptim (see
# build_wheels.sh). Build tools stay in this stage and do not end up in the
# final image.
FROM python:3.14.10-slim-trixie AS wheels
COPY build_wheels.sh /tmp/build_wheels.sh
RUN sh /tmp/build_wheels.sh


FROM python:3.14.10-slim-trixie

ARG NOVNC_VERSION=1.7.0

# Xvfb: virtual X display, x11vnc: VNC server for it, Mesa: software OpenGL
# (llvmpipe), matchbox: tiny window manager that shows each window fullscreen,
# libx*: runtime libraries GLFW loads, libxcb-*/libxkbcommon*/libegl1: what
# Qt (bioviz's GUI) needs to open X11 windows.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      xvfb x11vnc matchbox-window-manager \
      libgl1 libglx-mesa0 libgl1-mesa-dri \
      libxrandr2 libxinerama1 libxcursor1 libxi6 \
      libegl1 libxkbcommon0 libxkbcommon-x11-0 libxcb-cursor0 libxcb-icccm4 \
      libxcb-image0 libxcb-keysyms1 libxcb-render-util0 libxcb-shape0 libxcb-xkb1 \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir -m 1777 -p /tmp/.X11-unix

# noVNC web client (static files only).
ADD https://github.com/novnc/noVNC/archive/refs/tags/v${NOVNC_VERSION}.tar.gz /tmp/novnc.tar.gz
RUN mkdir /opt/novnc \
 && tar -xzf /tmp/novnc.tar.gz -C /opt/novnc --strip-components=1 \
 && rm -rf /tmp/novnc.tar.gz /opt/novnc/docs /opt/novnc/tests /opt/novnc/snap \
 && echo '<meta http-equiv="refresh" content="0; url=vnc.html?autoconnect=true&reconnect=true&resize=scale">' \
      > /opt/novnc/index.html

# PyQt6 ships all of Qt (~270 MB). bioviz and matplotlib only use the widget
# modules, so the rest (QML/Quick, 3D, multimedia, ...) is removed.
COPY requirements.txt /tmp/requirements.txt
RUN --mount=type=bind,from=wheels,source=/wheels,target=/tmp/wheels \
    pip install --no-cache-dir --no-deps -r /tmp/requirements.txt /tmp/wheels/*.whl \
 && cd "$(python -c 'import os, PyQt6; print(os.path.dirname(PyQt6.__file__))')" \
 && keep='Core|Gui|Widgets|DBus|OpenGL|OpenGLWidgets|Svg|SvgWidgets|PrintSupport' \
 && find . -maxdepth 1 -name 'Qt*.abi3.so' | grep -Ev "^\./Qt($keep)\.abi3\.so$" | xargs rm \
 && find Qt6/lib -type f | grep -Ev "/lib(Qt6($keep|XcbQpa)|icu[a-z0-9]+)\.so" | xargs rm \
 && cd Qt6/plugins \
 && ls | grep -Evx 'platforms|xcbglintegrations|imageformats|iconengines|platforminputcontexts' | xargs rm -r \
 && rm imageformats/libqpdf.so \
 && rm -rf ../qml ../translations ../qsci

# Lets Ctrl+C close `python -m mujoco.viewer` (see sitecustomize.py).
COPY sitecustomize.py /tmp/sitecustomize.py
RUN mv /tmp/sitecustomize.py "$(python -c 'import sysconfig; print(sysconfig.get_path("purelib"))')"

COPY --chmod=755 entrypoint.sh /usr/local/bin/entrypoint.sh

# On Linux, files the container writes to the shared folder belong to this
# user's IDs on the host, so compose.yaml passes the host user's IDs (set in
# .env, see README). Docker Desktop (macOS, Windows) maps ownership itself.
ARG UID=1000
ARG GID=1000
RUN groupadd --non-unique --gid "$GID" student \
 && useradd --non-unique --create-home --uid "$UID" --gid "$GID" student
USER student
WORKDIR /workspace

ENV DISPLAY=:0
EXPOSE 6080
ENTRYPOINT ["entrypoint.sh"]
CMD ["sleep", "infinity"]
