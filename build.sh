#!/bin/bash
# Build and test release packages for uyuni-retail components.
# All build/test operations run against origin/master via a temporary git worktree.
# Local uncommitted changes are never included in release artifacts.

set -euo pipefail

# SYNC: If you change this list, update PACKAGES in Makefile too
PACKAGES=(
    branch-network-formula
    dracut-saltboot
    dracut-wireless
    image-server-tools
    image-sync-formula
    kiwi-desc-saltboot
    POS_Image-Graphical6
    POS_Image-Graphical7
    POS_Image-JeOS6
    POS_Image-JeOS7
    python-susemanager-retail
    saltboot-formula
)

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

# --- Core operations (run inside worktree) ---

get_version() {
    local pkg="$1"
    grep -i '^Version:' "${pkg}/${pkg}.spec" | awk '{print $2}'
}

build_package() {
    local pkg="$1"
    local version
    version="$(get_version "$pkg")"

    echo "📦 Packaging ${pkg} version ${version}..."
    mkdir -p "packages/${pkg}"
    tar -czf "packages/${pkg}/${pkg}-${version}.tar.gz" \
        --transform="s,^${pkg},${pkg}-${version}," \
        "${pkg}"
    cp "${pkg}/${pkg}.spec"    "packages/${pkg}/"
    cp "${pkg}/${pkg}.changes" "packages/${pkg}/"
    echo "   -> Artifacts collected in packages/${pkg}/"
}

do_build_all() {
    for pkg in "${PACKAGES[@]}"; do
        build_package "$pkg"
    done
    echo "✅ All packages built successfully."
}

do_build_package() {
    local pkg="$1"
    build_package "$pkg"
}

do_test() {
    echo "🧪 Running version consistency tests..."
    local failed=0
    for pkg in "${PACKAGES[@]}"; do
        echo "   -> Checking package: ${pkg}"
        local spec_version changelog_version
        spec_version="$(get_version "$pkg")"
        changelog_version="$(grep -m 1 -oP -- '- Update to version \K[0-9a-zA-Z._-]+' \
            "${pkg}/${pkg}.changes" 2>/dev/null || echo "not_found")"

        if [ -z "$spec_version" ]; then
            echo "      ❌ ERROR: Could not find version in ${pkg}/${pkg}.spec"
            failed=1
        elif [ "$changelog_version" = "not_found" ]; then
            echo "      ❌ ERROR: Could not find changelog version entry in ${pkg}/${pkg}.changes"
            echo "         (Expecting a line like '- Update to version ...')"
            failed=1
        elif [ "$spec_version" != "$changelog_version" ]; then
            echo "      ❌ ERROR: Version mismatch in ${pkg}!"
            echo "         Spec file:      ${spec_version}"
            echo "         Changelog file: ${changelog_version}"
            failed=1
        else
            echo "      ✅ OK: Version ${spec_version} matches in spec and changelog."
        fi
    done
    if [ "$failed" -ne 0 ]; then
        echo "❌ Some tests failed."
        return 1
    fi
    echo "🎉 All tests passed."
}

# --- Worktree orchestration ---

# Runs this script inside a clean worktree at origin/master.
# mode: "build" — copies packages/ back to repo root after success
#       "test"  — no artifact copy
with_worktree() {
    local mode="$1"
    shift  # remaining args: command to run inside worktree

    local wtdir
    wtdir="$(mktemp -d)"
    cleanup() {
        if git -C "$REPO_ROOT" worktree list --porcelain | grep -Fxq "worktree $wtdir"; then
            git -C "$REPO_ROOT" worktree remove --force "$wtdir" || true;
	fi
	rm -rf "$wtdir"
    }
    trap cleanup RETURN

    echo "🔄 Fetching origin..."
    git -C "$REPO_ROOT" fetch origin
    git -C "$REPO_ROOT" worktree add "$wtdir" origin/master
    echo "   -> Worktree at ${wtdir}"

    # Devel: uncomment to copy this script into the worktree
    # cp "$REPO_ROOT/build.sh" "$wtdir/build.sh"

    local rc=0
    (cd "$wtdir" && _IN_WORKTREE=1 bash build.sh "$@") || rc=$?

    if [ "$rc" -eq 0 ] && [ "$mode" = "build" ]; then
        cp -r "${wtdir}/packages" "${REPO_ROOT}/"
        echo "✅ Artifacts copied to ${REPO_ROOT}/packages/"
    fi

    return "$rc"
}

# --- Clean (no worktree needed) ---

do_clean() {
    echo "🧹 Cleaning up build artifacts..."
    rm -rf "${REPO_ROOT}/packages"
}

# --- Dispatch ---

TARGET="${1:-all}"

# When running inside a worktree (_IN_WORKTREE=1), execute core operations directly
if [ "${_IN_WORKTREE:-0}" = "1" ]; then
    case "$TARGET" in
        all)             do_build_all ;;
        test)            do_test ;;
        *)               do_build_package "$TARGET" ;;
    esac
    exit 0
fi

# Outer invocation: use worktree for all targets except clean
case "$TARGET" in
    clean)
        do_clean
        ;;
    test)
        with_worktree test test
        ;;
    all)
        with_worktree build all
        ;;
    *)
        # Validate package name before spinning up worktree
        found=0
        for pkg in "${PACKAGES[@]}"; do
            if [ "$TARGET" = "$pkg" ]; then found=1; break; fi
        done
        if [ "$found" -eq 0 ]; then
            echo "❌ Unknown target: ${TARGET}"
            echo "Usage: $0 [all|test|clean|<package-name>]"
            echo "Packages: ${PACKAGES[*]}"
            exit 1
        fi
        with_worktree build "$TARGET"
        ;;
esac
