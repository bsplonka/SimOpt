# Runs at the start of every Python process in the container.
#
# Make Ctrl+C close the standalone viewer (`python -m mujoco.viewer`). Python
# only reacts to Ctrl+C between bytecode instructions, and the viewer's C++
# render loop never returns to Python, so restore the default action
# (terminate) for that command only.
import signal
import sys

_argv = sys.orig_argv
if "-m" in _argv and _argv[_argv.index("-m") + 1:][:1] == ["mujoco.viewer"]:
    signal.signal(signal.SIGINT, signal.SIG_DFL)
