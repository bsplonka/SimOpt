"""Shows a biorbd model in bioviz and animates it (raises the right arm).

Run in the container:  python bioviz_demo/demo.py
The window appears in the browser display (http://localhost:6080).
"""

from pathlib import Path

import bioviz
import numpy as np

viz = bioviz.Viz(str(Path(__file__).with_name("pyomecaman.bioMod")))

# One column of joint angles per frame. DoF 4 is the right arm's rotation about x.
n_frames = 100
q = np.zeros((viz.nQ, n_frames))
q[4] = np.linspace(0, np.pi / 2, n_frames)

viz.load_movement(q)  # adds a play button and a time slider
viz.exec()  # runs until the window is closed
