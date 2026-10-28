#!/usr/bin/env python3
"""Generate the MuJoCo model of the TIAGo Pro SEA arm from PAL Robotics' official
ROS 2 description (https://github.com/pal-robotics/pal_sea_arm).
"""

import io
import shutil
import sys
import tarfile
import tempfile
import types
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import fast_simplification
import mujoco
import numpy as np
import xacro

# Official PAL Robotics repositories, pinned to exact commits.
REPOS = {
    "pal_sea_arm": "ab41a838de6ecfe636c41c21d479799ae608f15b",  # 2.9.0
    "pal_pro_gripper": "ed9445716b9534b6d387d88eaf88f0bcb781b5cd",
    "pal_urdf_utils": "e8600a339a3a9b7ffe67d1030190b97b67fb577b",
}

# TIAGo Pro defaults (tiago_pro_robot: tiago_pro_description/config/*.yaml).
XACRO_ARGS = {
    "arm_type": "tiago-pro",
    "wrist_model": "spherical-wrist",
    "tool_changer": "True",
    "end_effector": "pal-pro-gripper",
    "ft_sensor": "no-ft-sensor",
}

# Position-servo gains (kp, kv) from pal_sea_arm_description/mujoco/mj_tags.xacro.
GAINS = {1: (1000, 50), 2: (1000, 60), 3: (1000, 50), 4: (500, 20),
         5: (1000, 20), 6: (1000, 20), 7: (500, 20)}

# Reflected motor inertia (kg m^2), which the URDF does not model. Without it the
# wrist (6e-4 kg m^2) chatters as soon as its torque saturates. 0.1 is the value
# MuJoCo Menagerie uses for comparable arms (e.g. Franka).
ARMATURE = 0.1

# Fraction of triangles removed from closed visual meshes (base, gripper fingers).
VISUAL_MESH_REDUCTION = 0.8

HOME = [-3.0, -1.15, -0.56, -1.58, 1.28, 1.78, 0.67]  # TCP at (0.5, 0, 0.6), tilted 30° down

OUT = Path("exercises/01_inverse_kinematics/models/tiago_pro_arm")


def fetch_repos(dest: Path) -> dict[str, Path]:
    """Downloads the pinned repos and returns {ros_package_name: package_dir}."""
    for repo, commit in REPOS.items():
        url = f"https://github.com/pal-robotics/{repo}/archive/{commit}.tar.gz"
        print(f"Downloading {url}")
        with urllib.request.urlopen(url) as resp:
            tarfile.open(fileobj=io.BytesIO(resp.read())).extractall(dest, filter="data")
    return {ET.parse(p).findtext("name"): p.parent for p in dest.glob("**/package.xml")}


STL_TRIANGLE = np.dtype([("normal", "<f4", 3), ("verts", "<f4", (3, 3)), ("attr", "<u2")])


def read_stl(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Binary STL -> (vertices, faces) with shared vertices."""
    data = path.read_bytes()
    n = int.from_bytes(data[80:84], "little")
    assert len(data) == 84 + n * STL_TRIANGLE.itemsize, f"{path} is not a binary STL"
    tris = np.frombuffer(data, STL_TRIANGLE, count=n, offset=84)["verts"]
    verts, faces = np.unique(tris.reshape(-1, 3), axis=0, return_inverse=True)
    return verts, faces.reshape(-1, 3)


def write_stl(path: Path, verts: np.ndarray, faces: np.ndarray) -> None:
    tris = np.zeros(len(faces), STL_TRIANGLE)
    tris["verts"] = verts[faces]
    normal = np.cross(tris["verts"][:, 1] - tris["verts"][:, 0],
                      tris["verts"][:, 2] - tris["verts"][:, 0])
    tris["normal"] = normal / (np.linalg.norm(normal, axis=1, keepdims=True) + 1e-12)
    path.write_bytes(bytes(80) + len(faces).to_bytes(4, "little") + tris.tobytes())


def is_closed(faces: np.ndarray) -> bool:
    """True if (almost) every edge is shared by two triangles."""
    edges = np.sort(faces[:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2), axis=1)
    _, count = np.unique(edges, axis=0, return_counts=True)
    return np.mean(count == 1) < 0.01


def install_ament_shim(packages: dict[str, Path]) -> None:
    """Lets xacro resolve $(find pkg) without a ROS installation."""
    shim = types.ModuleType("ament_index_python.packages")
    shim.get_package_share_directory = lambda name: str(packages[name])
    sys.modules["ament_index_python"] = types.ModuleType("ament_index_python")
    sys.modules["ament_index_python.packages"] = shim


def make_urdf(packages: dict[str, Path], mesh_dir: Path) -> str:
    xacro_file = packages["pal_sea_arm_description"] / "robots/pal_sea_arm.urdf.xacro"
    doc = xacro.process_file(str(xacro_file), mappings=XACRO_ARGS)
    robot = ET.fromstring(doc.toxml())

    # ROS/Gazebo-only elements.
    for tag in ("gazebo", "transmission", "ros2_control"):
        for el in robot.findall(tag):
            robot.remove(el)

    # Freeze the gripper fingers: the IK exercise only deals with the 7 arm joints.
    for joint in robot.findall("joint"):
        if joint.get("name").startswith("gripper_") and joint.get("type") != "fixed":
            joint.set("type", "fixed")
            for child in joint.findall("mimic") + joint.findall("limit"):
                joint.remove(child)

    # package://pkg/meshes/... -> flat, unique file names next to the MJCF:
    # <name>.stl (visual) and <name>_collision.stl.
    mesh_dir.mkdir(parents=True)
    for kind in ("visual", "collision"):
        for mesh in (m for el in robot.iter(kind) for m in el.iter("mesh")):
            pkg, rel = mesh.get("filename").removeprefix("package://").split("/", 1)
            name = Path(rel).stem.removesuffix("_collision")
            if pkg == "pal_pro_gripper_description":
                name = "gripper_" + name
            name += ".stl" if kind == "visual" else "_collision.stl"
            src, dst = packages[pkg] / rel, mesh_dir / name
            if not dst.exists():
                verts, faces = read_stl(src)
                # Decimating open CAD shells (most arm links) tears holes into them.
                if kind == "visual" and is_closed(faces):
                    write_stl(dst, *fast_simplification.simplify(
                        verts, faces, target_reduction=VISUAL_MESH_REDUCTION, agg=2))
                else:
                    shutil.copyfile(src, dst)
            mesh.set("filename", name)

    ET.SubElement(ET.SubElement(robot, "mujoco"), "compiler", {
        "meshdir": mesh_dir.name, "balanceinertia": "true",
        "discardvisual": "false", "fusestatic": "false"})
    return ET.tostring(robot, encoding="unicode")


def make_mjcf(urdf_file: Path) -> str:
    spec = mujoco.MjSpec.from_file(str(urdf_file))
    spec.modelname = "tiago_pro_arm"

    # Explicit Euler is unstable here: the wrist's inertia (6e-4 kg m^2) is too
    # small for kv = 20 at dt = 2 ms, and the arm shakes.
    spec.option.integrator = mujoco.mjtIntegrator.mjINT_IMPLICITFAST

    # The base is welded to the world, so MuJoCo does not filter this parent-child
    # contact by itself; the meshes overlap by 2.5 mm.
    spec.add_exclude(bodyname1="arm_root_link", bodyname2="arm_1_link")

    # Visual geoms in group 2, collision geoms in group 3 (hidden by default).
    for geom in spec.geoms:
        if geom.contype == 0:
            geom.group = 2
            geom.density = 0
        else:
            geom.group = 3
            geom.rgba = [0.6, 0.3, 0.3, 0.5]

    # Tool centre point between the gripper fingers (x: approach direction).
    spec.body("gripper_grasping_link").add_site(
        name="tcp", size=[0.008, 0, 0], rgba=[0.9, 0.1, 0.1, 1])

    for i, (kp, kv) in GAINS.items():
        joint = spec.joint(f"arm_{i}_joint")
        joint.armature = ARMATURE
        spec.add_actuator(
            name=f"arm_{i}", target=joint.name, trntype=mujoco.mjtTrn.mjTRN_JOINT,
            gaintype=mujoco.mjtGain.mjGAIN_FIXED, gainprm=[kp] + [0] * 9,
            biastype=mujoco.mjtBias.mjBIAS_AFFINE, biasprm=[0, -kp, -kv] + [0] * 7,
            ctrlrange=joint.range, ctrllimited=mujoco.mjtLimited.mjLIMITED_TRUE,
            # Effort limits from the URDF (43 Nm for joints 1-2, 26 Nm for 3-7).
            forcerange=joint.actfrcrange, forcelimited=mujoco.mjtLimited.mjLIMITED_TRUE)

    spec.add_key(name="home", qpos=HOME, ctrl=HOME)
    return spec.to_xml()


def main() -> None:
    shutil.rmtree(OUT / "meshes", ignore_errors=True)  # keep the hand-written scene.xml
    with tempfile.TemporaryDirectory() as tmp:
        packages = fetch_repos(Path(tmp))
        install_ament_shim(packages)
        urdf_file = OUT / "tiago_pro_arm.urdf"  # next to meshes/, removed below
        urdf_file.write_text(make_urdf(packages, OUT / "meshes"))
        shutil.copyfile(packages["pal_sea_arm_description"].parent / "LICENSE",
                        OUT / "LICENSE")
    (OUT / "tiago_pro_arm.xml").write_text(make_mjcf(urdf_file))
    urdf_file.unlink()
    print(f"Wrote {OUT}/tiago_pro_arm.xml")


if __name__ == "__main__":
    main()
