# SimOpt

Exercise environment for the course *Simulation and Optimization in Robotics and
Biomechanics*. It is a single Docker container with everything the exercises need:

- **biorbd** and **bioviz** for biomechanical models
- **MuJoCo** for physics simulation

Using a container means, that everyone is using the same setup and no one needs to install anything but the container once. 
You will write the code in the `exercises/` folder with any editor (like VS code, pycharm, ..., VIM) you like and run it in the container. The simulation viewers open **in your web browser**.

The commands are the same on macOS, Linux and Windows, on both Intel/AMD (x86-64) and ARM
processors.

## How to run

First install Docker and Git once, as described for your system under [Platforms](#platforms).
Then run the commands below in a terminal (Terminal on macOS and Linux, PowerShell on Windows).

**1. Get the code**

```bash
git clone https://github.com/bsplonka/SimOpt.git
cd SimOpt
```

Run all of the following commands in this `SimOpt` folder.

**2. Start the container**

```bash
docker compose up -d --build
```

The first start builds the container and takes a few minutes. On ARM processors (Apple
silicon Macs, Windows on Arm, ARM Linux) it takes about 10 minutes, because biorbd is
compiled there. Later starts take a few seconds.

**3. Open the display**

Open **http://localhost:6080** in your browser. The page stays black until a viewer is open.

**4. Run a simulation**

The MuJoCo viewer with the TIAGo Pro arm of exercise 1:

```bash
docker compose exec mujoco python -m mujoco.viewer --mjcf=01_inverse_kinematics/models/tiago_pro_arm/scene.xml
```

A biorbd model in bioviz (an animated human model):

```bash
docker compose exec mujoco python bioviz_demo/demo.py
```

Your own scripts run the same way. Paths are relative to the `exercises/` folder:

```bash
docker compose exec mujoco python 01_inverse_kinematics/my_script.py
```

The window appears in the browser tab. To close it, press `Ctrl+C` in the terminal.
After `Ctrl+C`, bioviz prints a `KeyboardInterrupt` message, which is expected.

**5. Stop the container**

```bash
docker compose down
```

Your files in `exercises/` are kept. To continue later, start again with step 2.

## Platforms

- [Linux](#linux)
- [macOS](#macos)
- [Windows](#windows)

### Linux

This setup uses Docker Engine. Docker Desktop for Linux handles file ownership differently
and has not been tested with it. If Docker is already installed, check which one you have:

```bash
docker info --format '{{.OperatingSystem}}'
```

Docker Desktop prints `Docker Desktop`. Docker Engine prints the name of your distribution,
e.g. `Ubuntu 24.04 LTS` (put `sudo` in front if you get `permission denied`).

1. Install [Docker Engine](https://docs.docker.com/engine/install/) for your distribution,
   including the Compose plugin. Then follow
   [Manage Docker as a non-root user](https://docs.docker.com/engine/install/linux-postinstall/)
   so that `docker` works without `sudo`. Ie run:
   ```bash
   sudo groupadd docker
   sudo usermod -aG docker $USER
   newgrp docker
   ```
2. Install Git, e.g. `sudo apt install git` (Debian, Ubuntu) or `sudo dnf install git` (Fedora).
3. After cloning (step 1 of [How to run](#how-to-run)), run this once in the `SimOpt` folder:

   ```bash
   printf 'UID=%s\nGID=%s\n' "$(id -u)" "$(id -g)" > .env
   ```

   It tells the container your user and group ID, so that files the container writes to
   `exercises/` belong to you. If you started the container before creating `.env`, run
   `docker compose up -d --build` again.

Then continue with [How to run](#how-to-run), and do step 3 above right after cloning.

### macOS

1. Install [Docker Desktop for Mac](https://docs.docker.com/desktop/setup/install/mac-install/).
   Download the version for your Mac's chip, shown under Apple menu → **About This Mac**:
   *Apple M…* means Apple silicon, *Intel* means Intel.
2. Start Docker Desktop. It must be running (whale icon in the menu bar) whenever you use
   the container.
3. Git: run `git --version` in Terminal. If Git is missing, macOS offers to install it.

Then continue with [How to run](#how-to-run).

### Windows

1. Install [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/).
   Download the version for your processor, shown under Settings → System → **About** →
   *System type*: *x64-based* or *ARM-based*. Docker labels its ARM version as Early Access.
   The installer sets up WSL 2; restart your computer if it asks you to.
2. Start Docker Desktop. It must be running (whale icon in the taskbar) whenever you use
   the container.
3. Install [Git for Windows](https://git-scm.com/downloads/win). The default options are fine.

Then continue with [How to run](#how-to-run), and run all commands in PowerShell.

## Troubleshooting

| Problem | Fix |
|---|---|
| `Cannot connect to the Docker daemon` or `docker` not found | Start Docker Desktop (macOS, Windows). On Linux, run `sudo systemctl start docker`. |
| `permission denied` on the Docker socket (Linux) | Do the [non-root user](https://docs.docker.com/engine/install/linux-postinstall/) step, then log out and in again. |
| Browser page is black | No viewer is open yet. Run step 4. |
| Port 6080 already in use | In `compose.yaml`, change `127.0.0.1:6080:6080` to e.g. `127.0.0.1:6081:6080` and open http://localhost:6081 |
| Image too small or blurry, or bioviz looks cramped | Change `SCREEN_SIZE` in `compose.yaml`, e.g. to `1920x1080`. The browser scales the image to fit the window. Larger sizes render more slowly. |
| Viewer feels sluggish | The container renders on the CPU, because Docker has no access to the graphics card. Keep shadows and reflections off: they are disabled in the scene, and switching them on under **Rendering** in the viewer costs about 3× the frame time. |
| `Permission denied` for files in `/workspace` (Linux) | Create `.env` as described under [Linux](#linux). On Fedora and other systems with SELinux, also change the volume in `compose.yaml` to `./exercises:/workspace:z`. |

## Repository layout

```
compose.yaml       how to start the container (the same on every platform)
docker/            Dockerfile, entrypoint and pinned Python requirements;
                   build_wheels.sh builds biorbd/ezc3d/bioviz where PyPI has no package
exercises/         your code: shared with the container as /workspace
  01_inverse_kinematics/
                   exercise 1, with the TIAGo Pro arm model
  bioviz_demo/     bioviz example (model from the bioviz repository, MIT license)
tools/             build_tiago_pro_arm.py: regenerates the TIAGo Pro arm model
                   from PAL Robotics' official repository (pinned commit)
```
