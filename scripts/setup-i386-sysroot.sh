#!/usr/bin/env bash
# Build an i386 (gcc -m32 / g++ -m32) sysroot under tools/i386-sysroot WITHOUT sudo,
# for linking / running the 1080 PC port (docs/1080_PC_PORT_PLAN.md section 13).
#
# Ubuntu / Debian only: the 32-bit libc + libgcc + libstdc++ packages are fetched with
# `apt-get download` (no root) and unpacked with `dpkg -x`, then fixed up so the host gcc
# can link against them. Also creates tools/cmake-venv (cmake + ninja) if it is missing.
#
# If gcc-multilib is already installed (`gcc -m32` links), the native toolchain is used
# and this script exits 0 without building anything. Equivalent root route:
#     sudo apt install gcc-multilib g++-multilib
#
# Safe to rerun: a finished sysroot (stamp .complete, written after the self-test passes) is
# only re-tested; the downloaded debs are cached in $SYSROOT_DIR/debs.
#
# Env overrides:
#   SYSROOT_DIR=<dir>   target directory           (default: <repo>/tools/i386-sysroot)
#   CMAKE_VENV=<dir>    cmake/ninja venv           (default: <repo>/tools/cmake-venv)
#   HOST_CC / HOST_CXX  host compilers             (default: gcc / g++)
#   FORCE=1             wipe root/ + wrappers and rebuild (keeps cached debs)
#   IGNORE_MULTILIB=1   build the sysroot even if gcc -m32 already works
#
# Usage afterwards:
#   tools/i386-sysroot/gcc32 hello.c -o hello && tools/i386-sysroot/run32 ./hello
#   PATH=tools/cmake-venv/bin:$PATH cmake -S <src> -B <build> -G Ninja \
#       -DCMAKE_TOOLCHAIN_FILE=$PWD/tools/i386-sysroot/toolchain-i386.cmake
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SYSROOT_DIR="${SYSROOT_DIR:-$REPO_ROOT/tools/i386-sysroot}"
CMAKE_VENV="${CMAKE_VENV:-$REPO_ROOT/tools/cmake-venv}"
HOST_CC="${HOST_CC:-gcc}"
HOST_CXX="${HOST_CXX:-g++}"

log() { echo "setup-i386-sysroot: $*"; }
die() { echo "setup-i386-sysroot: ERROR: $*" >&2; exit 1; }

mkdir -p "$(dirname "$SYSROOT_DIR")"
SYSROOT_DIR="$(cd "$(dirname "$SYSROOT_DIR")" && pwd)/$(basename "$SYSROOT_DIR")"

# ---------------------------------------------------------------- cmake / ninja venv
setup_cmake_venv() {
    if [[ -x "$CMAKE_VENV/bin/cmake" && -x "$CMAKE_VENV/bin/ninja" ]]; then
        log "cmake venv present: $CMAKE_VENV ($("$CMAKE_VENV/bin/cmake" --version | head -1))"
        return
    fi
    log "creating cmake venv: $CMAKE_VENV"
    if command -v uv >/dev/null 2>&1; then
        uv venv --quiet "$CMAKE_VENV"
        uv pip install --quiet --python "$CMAKE_VENV/bin/python" cmake ninja
    else
        python3 -m venv "$CMAKE_VENV"
        "$CMAKE_VENV/bin/pip" install --quiet cmake ninja
    fi
    "$CMAKE_VENV/bin/cmake" --version | head -1
    echo "ninja $("$CMAKE_VENV/bin/ninja" --version)"
}
setup_cmake_venv

# ---------------------------------------------------------------- native multilib?
command -v "$HOST_CC" >/dev/null 2>&1 || die "host compiler '$HOST_CC' not found"
if [[ "${IGNORE_MULTILIB:-0}" != 1 ]]; then
    probe="$(mktemp -d)"
    printf '#include <stdio.h>\nint main(void){puts("m32");return 0;}\n' > "$probe/t.c"
    if "$HOST_CC" -m32 "$probe/t.c" -o "$probe/t" >/dev/null 2>&1; then
        rm -rf "$probe"
        log "gcc-multilib is installed ('$HOST_CC -m32' links a hello world):"
        log "use the native toolchain (plain cmake / -m32); no sysroot needed."
        exit 0
    fi
    rm -rf "$probe"
fi

command -v apt-get >/dev/null 2>&1 || die "apt-get not found (Debian/Ubuntu only); install gcc-multilib some other way"
command -v dpkg >/dev/null 2>&1 || die "dpkg not found"
[[ "$("$HOST_CC" -dumpmachine)" == x86_64-linux-gnu ]] || die "host gcc is not x86_64-linux-gnu"

GCC_MAJOR="$("$HOST_CC" -dumpversion | cut -d. -f1)"
PKGS=(libc6-i386 libc6-dev-i386 lib32gcc-s1 "lib32gcc-${GCC_MAJOR}-dev" lib32stdc++6
      "lib32stdc++-${GCC_MAJOR}-dev" lib32quadmath0 lib32atomic1)
ROOT="$SYSROOT_DIR/root"
GCCDIR_REL="usr/lib/gcc/x86_64-linux-gnu/${GCC_MAJOR}/32"

# ---------------------------------------------------------------- build
build_sysroot() {
    log "building sysroot in $SYSROOT_DIR (gcc $GCC_MAJOR)"
    rm -rf "$ROOT" "$SYSROOT_DIR/test" "$SYSROOT_DIR/.complete"
    mkdir -p "$SYSROOT_DIR/debs" "$ROOT"

    # 1. download (cached)
    local need=()
    for p in "${PKGS[@]}"; do
        compgen -G "$SYSROOT_DIR/debs/${p}_*.deb" >/dev/null || need+=("$p")
    done
    if ((${#need[@]})); then
        log "apt-get download ${need[*]}"
        (cd "$SYSROOT_DIR/debs" && apt-get download "${need[@]}")
    fi

    # 2. extract
    for p in "${PKGS[@]}"; do
        local deb
        deb="$(ls -1 "$SYSROOT_DIR/debs/${p}_"*.deb | sort -V | tail -1)"
        dpkg -x "$deb" "$ROOT"
    done

    # 3. usrmerge: root/lib32/* -> root/usr/lib32, root/lib32 -> usr/lib32 (so the gcc dir's
    #    ../../../../../lib32/libstdc++.so.6 relative links resolve)
    mkdir -p "$ROOT/usr/lib32"
    if [[ -d "$ROOT/lib32" && ! -L "$ROOT/lib32" ]]; then
        cp -a "$ROOT/lib32/." "$ROOT/usr/lib32/"
        rm -rf "$ROOT/lib32"
    fi
    ln -sfn usr/lib32 "$ROOT/lib32"

    # 4. absolute symlinks (e.g. usr/lib32/libm.so -> /lib32/libm.so.6) -> relative, in-tree
    local link tgt new
    while IFS= read -r -d '' link; do
        tgt="$(readlink "$link")"
        [[ "$tgt" == /* ]] || continue
        new="$ROOT${tgt/#\/lib32\//\/usr\/lib32\/}"
        ln -sfn "$(realpath -ms --relative-to="$(dirname "$link")" "$new")" "$link"
    done < <(find "$ROOT" -type l -print0)

    # 5. ld scripts (libc.so) with absolute /lib32, /usr/lib32, /lib/ld-linux.so.2 paths -> absolute paths in-tree
    local f
    while IFS= read -r -d '' f; do
        grep -q 'GNU ld script' "$f" 2>/dev/null || continue
        grep -Eq '[ (]/(usr/)?lib(32)?/' "$f" || continue
        sed -E -i -e "s|([ (])/(usr/)?lib32/|\1$ROOT/usr/lib32/|g" \
                  -e "s|([ (])/lib/ld-linux\.so\.2|\1$ROOT/usr/lib32/ld-linux.so.2|g" "$f"
        log "rewrote ld script ${f#"$SYSROOT_DIR"/}"
    done < <(find "$ROOT/usr/lib32" -maxdepth 1 -type f -name '*.so' -size -4k -print0)

    # 6. the PT_INTERP path /lib/ld-linux.so.2, in-tree
    mkdir -p "$ROOT/lib"
    ln -sfn ../usr/lib32/ld-linux.so.2 "$ROOT/lib/ld-linux.so.2"

    [[ -f "$ROOT/usr/lib32/libc.so.6" && -f "$ROOT/$GCCDIR_REL/crtbegin.o" ]] \
        || die "extraction incomplete (missing libc.so.6 or $GCCDIR_REL/crtbegin.o)"
}

# ---------------------------------------------------------------- wrappers + toolchain
write_wrappers() {
    cat > "$SYSROOT_DIR/gcc32" <<EOF
#!/bin/sh
# gcc -m32 using the extracted i386 sysroot (no gcc-multilib needed).
# Generated by scripts/setup-i386-sysroot.sh.
R="\$(cd "\$(dirname "\$0")" && pwd)/root"
G="\$R/$GCCDIR_REL"
L="\$R/usr/lib32"
exec "\${HOST_CC:-gcc}" -m32 -B"\$G/" -B"\$L/" -L"\$G" -L"\$L" \\
  -idirafter /usr/include/x86_64-linux-gnu -idirafter "\$R/usr/include/x86_64-linux-gnu" \\
  -Wl,-rpath-link,"\$L" "\$@"
EOF
    cat > "$SYSROOT_DIR/g++32" <<EOF
#!/bin/sh
# g++ -m32 using the extracted i386 sysroot (no g++-multilib needed).
# Generated by scripts/setup-i386-sysroot.sh.
R="\$(cd "\$(dirname "\$0")" && pwd)/root"
G="\$R/$GCCDIR_REL"
L="\$R/usr/lib32"
exec "\${HOST_CXX:-g++}" -m32 -B"\$G/" -B"\$L/" -L"\$G" -L"\$L" \\
  -isystem "\$R/usr/include/x86_64-linux-gnu/c++/$GCC_MAJOR/32" \\
  -idirafter /usr/include/x86_64-linux-gnu -idirafter "\$R/usr/include/x86_64-linux-gnu" \\
  -Wl,-rpath-link,"\$L" "\$@"
EOF
    cat > "$SYSROOT_DIR/run32" <<'EOF'
#!/bin/sh
# Run a dynamically linked i386 binary with the extracted loader + libs.
# Generated by scripts/setup-i386-sysroot.sh.
R="$(cd "$(dirname "$0")" && pwd)/root"
exec "$R/usr/lib32/ld-linux.so.2" --library-path "$R/usr/lib32${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" "$@"
EOF
    chmod +x "$SYSROOT_DIR/gcc32" "$SYSROOT_DIR/g++32" "$SYSROOT_DIR/run32"

    cat > "$SYSROOT_DIR/toolchain-i386.cmake" <<'EOF'
# CMake toolchain: 32-bit x86 (i386) via the host gcc and the extracted sysroot next to
# this file (no gcc-multilib / sudo). Generated by scripts/setup-i386-sysroot.sh.
#   cmake -S <src> -B <build> -G Ninja -DCMAKE_TOOLCHAIN_FILE=<this file>
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR i686)
set(I386_SYSROOT_DIR "${CMAKE_CURRENT_LIST_DIR}")
set(CMAKE_C_COMPILER   "${I386_SYSROOT_DIR}/gcc32")
set(CMAKE_CXX_COMPILER "${I386_SYSROOT_DIR}/g++32")
set(CMAKE_ASM_COMPILER "${I386_SYSROOT_DIR}/gcc32")
# libraries/headers come from the wrapper flags; don't let find_* pick 64-bit libs
set(CMAKE_LIBRARY_ARCHITECTURE i386-linux-gnu)
set(CMAKE_FIND_ROOT_PATH "${I386_SYSROOT_DIR}/root")
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)
# Run built binaries (try_run, tests) through the extracted loader.
set(CMAKE_CROSSCOMPILING_EMULATOR "${I386_SYSROOT_DIR}/run32")
EOF

    cat > "$SYSROOT_DIR/README" <<EOF
i386 sysroot for gcc -m32 without gcc-multilib / sudo.
Generated by scripts/setup-i386-sysroot.sh (rerun it to rebuild; FORCE=1 to wipe first).
Packages (debs/, via apt-get download): ${PKGS[*]}
Fix-ups: usrmerge (root/lib32 -> usr/lib32), absolute symlinks made relative, libc.so ld
script rewritten with absolute paths into root/ (so after MOVING this directory, rerun the
script with FORCE=1), root/lib/ld-linux.so.2 -> ../usr/lib32/ld-linux.so.2.

  ./gcc32 hello.c -o hello && ./run32 ./hello      (./g++32 for C++; -static also works)
  cmake ... -DCMAKE_TOOLCHAIN_FILE=$SYSROOT_DIR/toolchain-i386.cmake
Binaries' interpreter /lib/ld-linux.so.2 is absent on a non-multilib host, so run them via
./run32, or link with -Wl,--dynamic-linker=\$PWD/root/usr/lib32/ld-linux.so.2
-Wl,-rpath,\$PWD/root/usr/lib32 -Wl,--disable-new-dtags to run them directly.
See docs/1080_PC_PORT_PLAN.md section 13.
EOF
}

# ---------------------------------------------------------------- self-test
self_test() {
    local T="$SYSROOT_DIR/test"
    mkdir -p "$T"
    cat > "$T/hello.c" <<'EOF'
#include <stdio.h>
#include <math.h>
int main(void){printf("hello C, sizeof(void*)=%d sqrt2=%f\n",(int)sizeof(void*),sqrt(2.0));return 0;}
EOF
    cat > "$T/hello.cpp" <<'EOF'
#include <iostream>
#include <vector>
#include <string>
struct S{double d;long long q;};
int main(){std::vector<std::string>*v=new std::vector<std::string>{"hello","C++"};for(auto&s:*v)std::cout<<s<<" ";std::cout<<"alignof(S)="<<alignof(S)<<" sizeof(void*)="<<sizeof(void*)<<std::endl;delete v;try{throw 42;}catch(int e){std::cout<<"exception ok "<<e<<std::endl;}}
EOF
    log "self-test:"
    "$SYSROOT_DIR/gcc32" -O2 "$T/hello.c" -o "$T/hello_c" -lm
    "$SYSROOT_DIR/g++32" -O2 -malign-double "$T/hello.cpp" -o "$T/hello_cpp"
    "$SYSROOT_DIR/gcc32" -O2 -static "$T/hello.c" -o "$T/hello_c_static" -lm
    local out_c out_cpp out_s
    out_c="$("$SYSROOT_DIR/run32" "$T/hello_c")"
    out_cpp="$("$SYSROOT_DIR/run32" "$T/hello_cpp")"
    out_s="$("$T/hello_c_static")"
    echo "  $(file -b "$T/hello_c" | cut -d, -f1-2)"
    echo "  run32 hello_c:      $out_c"
    echo "  run32 hello_cpp:    $(echo "$out_cpp" | tr '\n' '|')"
    echo "  hello_c_static:     $out_s"
    [[ "$out_c" == *"sizeof(void*)=4"* && "$out_s" == *"sizeof(void*)=4"* ]] || die "C self-test failed"
    [[ "$out_cpp" == *"hello C++"*"sizeof(void*)=4"*"exception ok 42"* ]] || die "C++ self-test failed"

    if [[ -x "$CMAKE_VENV/bin/cmake" ]]; then
        local C="$T/cmake"
        rm -rf "$C"; mkdir -p "$C/src"
        cp "$T/hello.cpp" "$C/src/"
        printf 'cmake_minimum_required(VERSION 3.16)\nproject(h CXX)\nadd_executable(h hello.cpp)\n' > "$C/src/CMakeLists.txt"
        PATH="$CMAKE_VENV/bin:$PATH" cmake -S "$C/src" -B "$C/build" -G Ninja \
            -DCMAKE_TOOLCHAIN_FILE="$SYSROOT_DIR/toolchain-i386.cmake" >/dev/null
        PATH="$CMAKE_VENV/bin:$PATH" cmake --build "$C/build" >/dev/null
        echo "  cmake+ninja hello:  $("$SYSROOT_DIR/run32" "$C/build/h" | head -1)"
    fi
    log "self-test PASSED"
}

if [[ "${FORCE:-0}" == 1 || ! -f "$SYSROOT_DIR/.complete" ]]; then
    build_sysroot
    write_wrappers
    self_test
    touch "$SYSROOT_DIR/.complete"   # only after a passing self-test
else
    log "sysroot present: $SYSROOT_DIR (FORCE=1 to rebuild)"
    self_test
fi
