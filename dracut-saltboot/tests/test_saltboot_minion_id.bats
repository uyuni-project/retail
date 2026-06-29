#!/usr/bin/env bats

setup() {
    . tests/test_helper.sh
    # Source the script directly - the guard prevents execution of main
    . saltboot/saltboot.sh
    
    # Mock Echo
    Echo() {
        echo "$@"
    }
    export -f Echo
    
    # Mock sleep
    sleep() {
        :
    }
    export -f sleep
    
    # Mock reboot
    reboot() {
        echo "REBOOT"
        exit 1
    }
    export -f reboot
    
    # Mock salt-call
    mock-salt-call() {
        :
    }
    export -f mock-salt-call
    export INITRD_SALT_CALL="mock-salt-call"
    
    # Setup mock environment
    export INITRD_SALT_ETC=$(mktemp -d)
    mkdir -p "$INITRD_SALT_ETC/minion.d"
    export MACHINE_ID="abcdef123456"
    export MINION_ID_PREFIX="terminal"
    
    # Reset variables
    unset USE_MAC_MINION_ID
    unset DISABLE_HOSTNAME_ID
    unset USE_FQDN_MINION_ID
    unset DISABLE_UNIQUE_SUFFIX
    unset DISABLE_ID_PREFIX
    unset HAVE_MINION_ID
    unset MINION_ID
    unset IPADDR
    unset INTERFACE
}

teardown() {
    rm -rf "$INITRD_SALT_ETC"
}

@test "MINION_ID from MAC address" {
    export USE_MAC_MINION_ID=1
    export INTERFACE=eth0
    export DISABLE_UNIQUE_SUFFIX=1
    
    ip() {
        echo "ether aa:bb:cc:dd:ee:ff"
    }
    export -f ip
    
    generate_minion_id
    
    assert "terminal.aa:bb:cc:dd:ee:ff" "$(cat $INITRD_SALT_ETC/minion_id)"
}

@test "MINION_ID from hostname (short)" {
    export IPADDR="10.0.0.1"
    export DISABLE_UNIQUE_SUFFIX=1
    
    dig() {
        echo "myhost.example.com."
    }
    export -f dig
    
    generate_minion_id
    
    assert "terminal.myhost" "$(cat $INITRD_SALT_ETC/minion_id)"
}

@test "MINION_ID from FQDN" {
    export IPADDR="10.0.0.1"
    export USE_FQDN_MINION_ID=1
    export DISABLE_UNIQUE_SUFFIX=1
    
    dig() {
        echo "myhost.example.com."
    }
    export -f dig
    
    generate_minion_id
    
    assert "terminal.myhost.example.com" "$(cat $INITRD_SALT_ETC/minion_id)"
}

@test "MINION_ID from SMBIOS when others fail" {
    # Neither MAC nor Hostname
    export DISABLE_HOSTNAME_ID=1
    export DISABLE_UNIQUE_SUFFIX=1
    
    export INITRD_SALT_CALL="mock-salt-call"
    mock-salt-call() {
        if [[ "$*" == *smbios.get\ system-manufacturer* ]]; then echo "DELL"; fi
        if [[ "$*" == *smbios.get\ system-product-name* ]]; then echo "OptiPlex"; fi
        if [[ "$*" == *smbios.get\ system-serial-number* ]]; then echo "123456"; fi
    }
    export -f mock-salt-call
    
    generate_minion_id
    
    assert "terminal.DELL-OptiPlex-123456" "$(cat $INITRD_SALT_ETC/minion_id)"
}

@test "MINION_ID with unique suffix" {
    export USE_MAC_MINION_ID=1
    export INTERFACE=eth0
    # DISABLE_UNIQUE_SUFFIX is unset
    
    ip() {
        echo "ether aa:bb:cc:dd:ee:ff"
    }
    export -f ip
    
    generate_minion_id
    
    # MACHINE_ID=abcdef123456, suffix should be -abcd
    assert "terminal.aa:bb:cc:dd:ee:ff-abcd" "$(cat $INITRD_SALT_ETC/minion_id)"
}
