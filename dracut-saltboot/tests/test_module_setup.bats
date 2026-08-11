#!/usr/bin/env bats

setup() {
    # Source the common test helper
    . tests/test_helper.sh
    # Source the script to get functions
    . saltboot/module-setup.sh
    
    # Mock rpm
    rpm() {
        local args="$*"
        if [[ "$args" =~ "-q --requires" ]]; then
            local pkgs="${args#*-q --requires }"
            for pkg in $pkgs; do
                if [[ "$pkg" == "pkgA" ]]; then
                    echo "python3-pkgB"
                    echo "python3-pkgC"
                elif [[ "$pkg" == "pkgB" ]]; then
                    echo "python3-pkgD"
                fi
            done
        elif [[ "$args" =~ "-q --whatprovides" ]]; then
            local req="${args#*-q --whatprovides }"
            if [[ "$req" == "python3-pkgB" ]]; then
                echo "pkgB"
            elif [[ "$req" == "python3-pkgC" ]]; then
                echo "pkgC"
            elif [[ "$req" == "python3-pkgD" ]]; then
                echo "pkgD"
            fi
        fi
    }
    export -f rpm
}

@test "get_python_pkg_deps finds direct python dependencies" {
    # get_python_pkg_deps pkgA
    # should return pkgB and pkgC
    
    run get_python_pkg_deps pkgA
    assert 0 "$status"

    sorted_output=$(echo "$output" | sort | xargs)
    assert "pkgB pkgC" "$sorted_output"
}

@test "get_python_pkg_deps_recursive finds all nested python dependencies" {
    # pkgA -> pkgB -> pkgD
    # pkgA -> pkgC
    
    run get_python_pkg_deps_recursive pkgA
    assert 0 "$status"

    sorted_output=$(echo "$output" | sort -u | xargs)
    assert "pkgA pkgB pkgC pkgD" "$sorted_output"
}
