#!/bin/sh
# Starts a virtual X display that is shown in the browser via noVNC
# (http://localhost:6080) -- unless the host's X socket directory is mounted
# into the container (native X11 forwarding, e.g. on Linux).
set -e

if ! grep -q " /tmp/.X11-unix " /proc/mounts; then
    # Left over from the previous run if the container was stopped and started.
    rm -f "/tmp/.X${DISPLAY#:}-lock" "/tmp/.X11-unix/X${DISPLAY#:}"

    Xvfb "$DISPLAY" -screen 0 "${SCREEN_SIZE:-1280x720}x24" -nolisten tcp >/dev/null 2>&1 &
    while [ ! -S "/tmp/.X11-unix/X${DISPLAY#:}" ]; do sleep 0.1; done

    # Shows each window fullscreen. The title bar has a close button and, on
    # the arrow, a list of all windows (bioptim opens several plots).
    matchbox-window-manager -use_titlebar yes >/dev/null 2>&1 &
    x11vnc -display "$DISPLAY" -localhost -rfbport 5900 -nopw -forever -shared \
        -wait 10 -defer 10 -quiet >/dev/null 2>&1 &
    websockify --web /opt/novnc 6080 localhost:5900 >/dev/null 2>&1 &
    echo "Display ready: open http://localhost:6080 in your browser."
fi

exec "$@"
