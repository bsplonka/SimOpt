#!/bin/sh
# Puts wheels into /wheels for the packages that a plain `pip install` from PyPI
# cannot provide (runs in the `wheels` stage of the Dockerfile):
#   - biorbd, biorbd_casadi and ezc3d: PyPI has Linux wheels for x86_64 only,
#     so on arm64 (e.g. Apple Silicon) they are built from source, which takes
#     ~10 minutes.
#   - bioviz and bioptim: not on PyPI at all, so they are built from their
#     GitHub releases.
set -e

BIORBD_VERSION=1.12.4
BIORBD_COMMIT=d460d66eb55338da51f725c6c55e60633769b038  # tag Release_1.12.4
EZC3D_VERSION=1.7.2
BIOVIZ_VERSION=2.5.2
BIOVIZ_COMMIT=8f84df46b30cd81a9c7e81b110e99c732b315a2d  # tag Release_2.5.2
BIOPTIM_COMMIT=fdafe4d9e50edb3f92a14f1980b08c3f81434545  # tag Release_3.4.0

# Pinned versions of the tools pip installs to build the packages. casadi is
# the version biorbd_casadi is compiled against; it must match requirements.txt.
cat > /tmp/build-constraints.txt <<EOF
casadi==3.8.1
cmake==4.4.4
distro==1.9.0
ninja==1.13.2
numpy==2.5.4
packaging==26.3
scikit-build==0.19.1
scipy==1.18.1
setuptools==84.2.1
setuptools-scm==10.3.4
swig==4.5.1
vcs-versioning==2.6.0
wheel==0.48.0
EOF
export PIP_BUILD_CONSTRAINT=/tmp/build-constraints.txt PIP_NO_CACHE_DIR=1 \
       PIP_ROOT_USER_ACTION=ignore PIP_DISABLE_PIP_VERSION_CHECK=1

apt-get update
apt-get install -y --no-install-recommends curl ca-certificates

fetch() {  # <url> <dir>: unpack a .tar.gz into <dir>
    mkdir -p "$2"
    curl -fsSL "$1" | tar -xz -C "$2" --strip-components=1
}

build() {  # <source dir> [auditwheel options]: build a wheel and bundle the
           # shared libraries it needs
    src=$1
    shift
    pip wheel --no-deps -w /tmp/raw "$src"
    auditwheel repair "$@" -w /wheels /tmp/raw/*.whl
    rm -rf /tmp/raw
}

mkdir -p /wheels
if ! pip download --no-deps --only-binary :all: -d /wheels "biorbd==$BIORBD_VERSION" \
        "biorbd-casadi==$BIORBD_VERSION" "ezc3d==$EZC3D_VERSION"; then
    echo "No biorbd/biorbd_casadi/ezc3d wheels on PyPI for $(uname -m), building them from source."
    rm -f /wheels/*
    apt-get install -y --no-install-recommends build-essential git patchelf
    pip install auditwheel==6.4.2 pyelftools==0.33 packaging==26.3

    fetch "https://files.pythonhosted.org/packages/source/e/ezc3d/ezc3d-$EZC3D_VERSION.tar.gz" /src/ezc3d
    build /src/ezc3d

    # Same source for both math backends, built in separate folders so that
    # the second build does not reuse the CMake cache of the first.
    fetch "https://github.com/pyomeca/biorbd/archive/$BIORBD_COMMIT.tar.gz" /src/biorbd
    cp -r /src/biorbd /src/biorbd_casadi
    MATH_LIBRARY_BACKEND=Eigen3 build /src/biorbd
    # Like the PyPI wheels, biorbd_casadi uses the library of the casadi
    # package instead of bundling a second copy.
    MATH_LIBRARY_BACKEND=Casadi build /src/biorbd_casadi --exclude libcasadi.so.3.7
fi

# bioviz's setup.py has no version, so pip would record it as 0.0.0.
fetch "https://github.com/pyomeca/bioviz/archive/$BIOVIZ_COMMIT.tar.gz" /src/bioviz
sed -i "s/name=\"bioviz\",/name=\"bioviz\", version=\"$BIOVIZ_VERSION\",/" /src/bioviz/setup.py
pip wheel --no-deps -w /wheels /src/bioviz

# bioptim 3.4.0 predates casadi 3.8 (required by biorbd_casadi 1.12.4),
# matplotlib 3.9 and Python 3.14, so it gets four small fixes:
#   - casadi 3.8 removed MX_eye/SX_eye/DM_eye; MX.eye etc. are the same.
#   - casadi 3.8 warns when numpy functions are called on casadi values, as
#     bioptim does. It still behaves as before (what bioptim is written for),
#     so the warning is switched off.
#   - matplotlib 3.9 removed matplotlib.cm.get_cmap; pyplot.get_cmap remains.
#   - Python 3.14 no longer starts processes with fork on Linux, but the live
#     plot of the optimization (show_online_optim) needs fork.
fetch "https://github.com/pyomeca/bioptim/archive/$BIOPTIM_COMMIT.tar.gz" /src/bioptim
cd /src/bioptim/bioptim
sed -i -E -e '/^from casadi import/ s/\b(MX|SX|DM)_eye\b/\1/g' -e 's/\b(MX|SX|DM)_eye\b/\1.eye/g' \
    $(grep -rlE '\b(MX|SX|DM)_eye\b' --include='*.py' .)
printf '\nimport casadi\n\ncasadi.GlobalOptions.setNumpyMode(-1)\n' >> __init__.py
sed -i -e 's/^from matplotlib\.cm import get_cmap$/from matplotlib.pyplot import get_cmap/' \
       -e 's/\bmcm\.get_cmap(/plt.get_cmap(/g' gui/ipopt_output_plot.py gui/check_conditioning.py
sed -i 's/^import multiprocessing as mp$/import multiprocessing\nmp = multiprocessing.get_context("fork")/' \
    gui/online_callback_multiprocess.py
if grep -rnE '\b(MX|SX|DM)_eye\b|cm import get_cmap|mcm\.get_cmap|^import multiprocessing as mp$' --include='*.py' .; then
    echo "bioptim patch did not apply" >&2
    exit 1
fi
cd /
pip wheel --no-deps -w /wheels /src/bioptim

ls -l /wheels
