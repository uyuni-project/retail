#!/usr/bin/env bats

setup() {
    # Source the common test helper
    . tests/test_helper.sh
    # Ensure saltboot-root.sh doesn't source /lib/dracut-lib.sh
    # By providing the mock functions in setup
    . tests/mocks/mock_dracut.sh
    export CMDLINE=""
    # Reset variables that might be set by saltboot-root.sh
    unset MASTER
    unset MINION_ID_PREFIX
    unset SALT_DEVICE
    unset SALT_TIMEOUT
    unset SALT_STOP_TIMEOUT
    unset SALT_START_TIMEOUT
    unset SALT_KEY_TIMEOUT
    unset DISABLE_UNIQUE_SUFFIX
    unset DISABLE_HOSTNAME_ID
    unset DISABLE_ID_PREFIX
    unset USE_FQDN_MINION_ID
    unset USE_MAC_MINION_ID
    unset KIWIDEBUG
    unset root
    unset rootok
    unset DHCPORSERVER
}

source_saltboot_root() {
    # Source the script and ignore its exit status (it might be non-zero due to assignments)
    . saltboot/saltboot-root.sh || true
}

@test "Default values without kernel arguments" {
    source_saltboot_root
    assert "" "$MASTER"
    assert "60" "$SALT_TIMEOUT"
    assert "15" "$SALT_STOP_TIMEOUT"
    assert "10" "$SALT_START_TIMEOUT"
    assert "60" "$SALT_KEY_TIMEOUT"
    assert "saltboot" "$root"
    assert "1" "$rootok"
    assert "1" "$DHCPORSERVER"
}

@test "Parsing master and prefix arguments" {
    export CMDLINE="rd.saltboot.master=myserver.com rd.saltboot.id_prefix=myprefix"
    source_saltboot_root
    assert "myserver.com" "$MASTER"
    assert "myprefix" "$MINION_ID_PREFIX"
}

@test "Parsing timeout arguments" {
    export CMDLINE="rd.saltboot.salt_timeout=120 rd.saltboot.salt_stop_timeout=30 rd.saltboot.salt_start_timeout=20 rd.saltboot.salt_key_timeout=300"
    source_saltboot_root
    assert "120" "$SALT_TIMEOUT"
    assert "30" "$SALT_STOP_TIMEOUT"
    assert "20" "$SALT_START_TIMEOUT"
    assert "300" "$SALT_KEY_TIMEOUT"
}

@test "Parsing timeout arguments with bounds" {
    export CMDLINE="rd.saltboot.salt_timeout=4000 rd.saltboot.salt_stop_timeout=-10"
    source_saltboot_root

    # If the value is out of range [min, max], it returns the default.
    assert "60" "$SALT_TIMEOUT" # default
    assert "15" "$SALT_STOP_TIMEOUT" # default
}

@test "Parsing boolean flags (present)" {
    export CMDLINE="rd.saltboot.nosuffix rd.saltboot.debug"
    source_saltboot_root
    assert "1" "$DISABLE_UNIQUE_SUFFIX"
    assert "1" "$KIWIDEBUG"
}

@test "Parsing boolean flags (yes/true)" {
    export CMDLINE="rd.saltboot.usefqdn=yes rd.saltboot.nohostname=true"
    source_saltboot_root
    assert "1" "$USE_FQDN_MINION_ID"
    assert "1" "$DISABLE_HOSTNAME_ID"
}

@test "Parsing boolean flags (no/false)" {
    export CMDLINE="rd.saltboot.usemac=no rd.saltboot.noprefix=off"
    source_saltboot_root
    assert "" "$USE_MAC_MINION_ID"
    assert "" "$DISABLE_ID_PREFIX"
}

@test "DHCPORSERVER should be unset if server is present" {
    server="1.2.3.4"
    source_saltboot_root
    assert "" "$DHCPORSERVER"
}

@test "Parsing legacy options" {
    export CMDLINE="MASTER=myserver.com MINION_ID_PREFIX=myprefix DISABLE_ID_PREFIX=1 salt_device=/dev/sda2"
    source_saltboot_root

    assert "myserver.com" "$MASTER"
    assert "myprefix" "$MINION_ID_PREFIX"
    assert "1" "$DISABLE_ID_PREFIX"
    assert "/dev/sda2" "$SALT_DEVICE"
}
