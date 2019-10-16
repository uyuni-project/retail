#!/bin/bash

# called by dracut
check() {
    return 0
}

# called by dracut
depends() {
    echo network
    echo crypt
    return 0
}

# called by dracut
installkernel() {
    instmods =drivers/net/wireless
}

# called by dracut
install() {
    inst_multiple -o wpa_supplicant wpa_passphrase wpa_cli
    inst_rules "$moddir/80-wireless.rules"
    inst_script "$moddir/wireless_up.sh" "/sbin/wireless_up"
    inst_script "$moddir/wireless_ask_password.sh" "/sbin/wireless_ask_password"
    inst_script "$moddir/wireless_ask_password_wrapper.sh" "/sbin/wireless_ask_password_wrapper"

    # include wlan configuration for wifi credentials, even in no-hostonly mode
    # if there is initrd-ifcfg-wlan*, prefer it over ifcfg-wlan*
    for f in /etc/sysconfig/network/initrd-ifcfg-wlan* ; do
        [ ! -f "$f" ] && continue
        inst "$f" "${f/initrd-/}"
    done
    for f in /etc/sysconfig/network/ifcfg-wlan* ; do
        [ ! -f "$f" ] && continue
        [ -f "${f/ifcfg-/initrd-ifcfg-/}" ] && continue
        inst "$f"
    done

    inst_hook pre-pivot 99 "$moddir/wireless_update.sh"
    inst_hook cleanup 99 "$moddir/wireless_cleanup.sh"
}

