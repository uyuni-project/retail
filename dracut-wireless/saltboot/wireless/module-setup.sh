#!/bin/bash

# called by dracut
check() {
    return 0
}

# called by dracut
depends() {
    echo network
    return 0
}

# called by dracut
installkernel() {
    instmods =drivers/net/wireless
}

# called by dracut
install() {
    inst_multiple -o wpa_supplicant wpa_passphrase
    inst_rules "$moddir/80-wireless.rules"
    inst_script "$moddir/wireless_up.sh" "/sbin/wireless_up"

    #include wlan configuration for wifi credentials, even in no-hostonly mode
    inst_multiple -o /etc/sysconfig/network/ifcfg-wlan*
    
    inst_hook pre-pivot 99 "$moddir/wireless_update.sh"
    inst_hook cleanup 99 "$moddir/wireless_cleanup.sh"
}

