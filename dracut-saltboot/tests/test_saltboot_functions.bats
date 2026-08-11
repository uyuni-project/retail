#!/usr/bin/env bats

setup() {
    . tests/test_helper.sh
    . saltboot/saltboot.sh
    
    # Mock Echo
    Echo() {
        echo "$@"
    }
    export -f Echo
    
    # Mock mount/umount
    mount() {
        return 0
    }
    export -f mount
    umount() {
        return 0
    }
    export -f umount

    INITRD_SALT_ETC_TMP=$(mktemp -d)
    export INITRD_SALT_ETC="$INITRD_SALT_ETC_TMP"
    export NEWROOT=$(mktemp -d)
    export SALT_DEVICE="/dev/sda1"
}

teardown() {
    rm -rf "$NEWROOT"
    rm -rf "$INITRD_SALT_ETC"
}

@test "configure_salt_vars: venv-salt-call" {
    is_venv_salt_call_installed() { return 0; }
    configure_salt_vars
    assert "/etc/venv-salt-minion" "$INITRD_SALT_ETC"
    assert "venv-salt-call" "$INITRD_SALT_CALL"
}

@test "configure_salt_vars: standard salt" {
    is_venv_salt_call_installed() { return 1; }
    configure_salt_vars
    assert "/etc/salt" "$INITRD_SALT_ETC"
    assert "salt-call" "$INITRD_SALT_CALL"
}

@test "load_existing_salt_config: finds config in etc/venv-salt-minion" {
    mkdir -p "$NEWROOT/etc/venv-salt-minion/minion.d"
    touch "$NEWROOT/etc/venv-salt-minion/minion_id"
    touch "$NEWROOT/etc/venv-salt-minion/minion.d/kiwi_activation_key.conf"
    
    load_existing_salt_config
    
    assert "y" "$HAVE_MINION_ID"
    [ -f "$INITRD_SALT_ETC/minion_id" ]
    [ ! -f "$INITRD_SALT_ETC/minion.d/kiwi_activation_key.conf" ]
}

@test "prepare_salt_config: generates susemanager.conf" {
    # Mock dig and salt-call
    export INITRD_SALT_CALL="mock-salt-call"
    mock-salt-call() {
        echo "salt-master.example.com"
    }
    export -f mock-salt-call
    
    mkdir -p "$INITRD_SALT_ETC/minion.d"
    
    prepare_salt_config
    
    [ -f "$INITRD_SALT_ETC/minion.d/susemanager.conf" ]
    grep -q "master: salt-master.example.com" "$INITRD_SALT_ETC/minion.d/susemanager.conf"
}

@test "prepare_autosigned_grains: creates config from SALT_AUTOSIGN_GRAINS" {
    export SALT_AUTOSIGN_GRAINS="grain1:val1,grain2,grain3:val3"
    mkdir -p "$INITRD_SALT_ETC/minion.d"
    
    prepare_autosigned_grains
    
    [ -f "$INITRD_SALT_ETC/minion.d/autosign-grains-onetime.conf" ]
    grep -q "grain1: val1" "$INITRD_SALT_ETC/minion.d/autosign-grains-onetime.conf"
    grep -q "grain3: val3" "$INITRD_SALT_ETC/minion.d/autosign-grains-onetime.conf"
    grep -q "    - grain2" "$INITRD_SALT_ETC/minion.d/autosign-grains-onetime.conf"
}
