#!/usr/bin/env bats

setup() {
    . tests/test_helper.sh
    . tests/mocks/mock_dracut.sh
    export -f getarg
    export -f getargnum
    export -f getargbool
    export -f str_replace
    
    export hookdir=$(mktemp -d)
    mkdir -p "$hookdir/initqueue/finished"
    export root=""
}

teardown() {
    rm -rf "$hookdir"
}

@test "Exits early if root is empty" {
    root=""
    run bash saltboot/saltboot-timeout.sh
    assert 0 "$status"
    assert "" "$output"
}

@test "Exits early if root is saltboot" {
    root="saltboot"
    run bash saltboot/saltboot-timeout.sh
    assert 0 "$status"
}

@test "Processes network and device wait scripts" {
    root="block:/dev/sda1"
    # _name should be block:\x2fdev\x2fsda1
    # wait-network.sh and devexists-block:\x2fdev\x2fsda1.sh
    
    touch "$hookdir/initqueue/finished/wait-network.sh"
    touch "$hookdir/initqueue/finished/devexists-\x2fdev\x2fsda1.sh"
    
    # Run the script
    run bash saltboot/saltboot-timeout.sh
    
    assert 0 "$status"
    # The script should have removed the files
    [ ! -e "$hookdir/initqueue/finished/wait-network.sh" ]
    [ ! -e "$hookdir/initqueue/finished/devexists-\x2fdev\x2fsda1.sh" ]
}

@test "Does not remove if scripts don't exist" {
    root="block:/dev/sda1"
    # Files don't exist, script should still exit 0
    run bash saltboot/saltboot-timeout.sh
    assert 0 "$status"
}
