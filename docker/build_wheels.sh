#!/bin/sh
# Puts wheels into /wheels for the packages that a plain `pip install` from PyPI
# cannot provide (runs in the `wheels` stage of the Dockerfile):
#   - biorbd and ezc3d: PyPI has Linux wheels for x86_64 only, so on arm64
#     (e.g. Apple Silicon) they are built from source, which takes ~5 minutes.
#   - bioviz: not on PyPI at all, so it is built from its GitHub release.
set -e

BIORBD_VERSION=1.12.4
BIORBD_COMMIT=d460d66eb55338da51f725c6c55e60633769b038  # tag Release_1.12.4
EZC3D_VERSION=1.7.2
BIOVIZ_VERSION=2.5.2
BIOVIZ_COMMIT=8f84df46b30cd81a9c7e81b110e99c732b315a2d  # tag Release_2.5.2

# Pinned versions of the tools pip installs to build the packages.
cat > /tmp/build-constraints.txt <<EOF
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

build() {  # <source dir>: build a wheel and bundle the shared libraries it needs
    pip wheel --no-deps -w /tmp/raw "$1"
    auditwheel repair -w /wheels /tmp/raw/*.whl
    rm -rf /tmp/raw
}

mkdir -p /wheels
if ! pip download --no-deps --only-binary :all: -d /wheels \
        "biorbd==$BIORBD_VERSION" "ezc3d==$EZC3D_VERSION"; then
    echo "No biorbd/ezc3d wheels on PyPI for $(uname -m), building them from source."
    rm -f /wheels/*
    apt-get install -y --no-install-recommends build-essential git patchelf
    pip install auditwheel==6.4.2 pyelftools==0.33 packaging==26.3

    fetch "https://files.pythonhosted.org/packages/source/e/ezc3d/ezc3d-$EZC3D_VERSION.tar.gz" /src/ezc3d
    build /src/ezc3d

    fetch "https://github.com/pyomeca/biorbd/archive/$BIORBD_COMMIT.tar.gz" /src/biorbd
    MATH_LIBRARY_BACKEND=Eigen3 build /src/biorbd
fi

# bioviz's setup.py has no version, so pip would record it as 0.0.0.
fetch "https://github.com/pyomeca/bioviz/archive/$BIOVIZ_COMMIT.tar.gz" /src/bioviz
sed -i "s/name=\"bioviz\",/name=\"bioviz\", version=\"$BIOVIZ_VERSION\",/" /src/bioviz/setup.py
pip wheel --no-deps -w /wheels /src/bioviz

ls -l /wheels
