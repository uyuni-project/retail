#!/bin/bash

# this is supposed to be executed before ifup from network module

PATH=/usr/sbin:/usr/bin:/sbin:/bin

type getarg >/dev/null 2>&1 || . /lib/dracut-lib.sh

# setup wlan

WLAN_DEV=$1

if [ -f "/etc/sysconfig/network/ifcfg-$WLAN_DEV" ]; then
    . /etc/sysconfig/network/ifcfg-$WLAN_DEV
fi

if getarg WIRELESS_WPA_PSK= >/dev/null ; then
    WIRELESS_WPA_PSK=$(getarg WIRELESS_WPA_PSK=)
fi

if getarg WIRELESS_ESSID= >/dev/null ; then
    WIRELESS_ESSID=$(getarg WIRELESS_ESSID=)
fi

if getarg WIRELESS_WPA_DRIVER= >/dev/null ; then
    WIRELESS_WPA_DRIVER=$(getarg WIRELESS_WPA_DRIVER=)
fi

if [ -n "$WIRELESS_ESSID" ]; then
    mkdir -p /etc/wpa_supplicant
    #try to write wpa configuration using cmdline args
    echo "ctrl_interface=/var/run/wpa_supplicant"         > /etc/wpa_supplicant/wpa_supplicant.conf
    echo "ctrl_interface_group=wheel"                    >> /etc/wpa_supplicant/wpa_supplicant.conf
    if [ -n "$WIRELESS_WPA_PSK" ]; then
        wpa_passphrase "$WIRELESS_ESSID" "$WIRELESS_WPA_PSK" >>/etc/wpa_supplicant/wpa_supplicant.conf
    else
        echo "network={"                    >>/etc/wpa_supplicant/wpa_supplicant.conf
        echo "    ssid=\"$WIRELESS_ESSID\"" >>/etc/wpa_supplicant/wpa_supplicant.conf
        echo "}"                            >>/etc/wpa_supplicant/wpa_supplicant.conf
    fi
    echo "WIRELESS_ESSID=$WIRELESS_ESSID" > /tmp/wireless-$WLAN_DEV
    echo "WIRELESS_WPA_PSK=$WIRELESS_WPA_PSK" >> /tmp/wireless-$WLAN_DEV
fi

if [ -z "$WIRELESS_WPA_DRIVER" ]; then
    WIRELESS_DRIVER="`( cd -P /sys/class/net/$WLAN_DEV/device/driver;echo ${PWD##*/}; )`"
    case "${WIRELESS_DRIVER}" in
        prism54)
            WIRELESS_WPA_DRIVER=prism54
            ;;
        rt61|rt73)
            WIRELESS_WPA_DRIVER=ralink
            ;;
        ath_pci)
            WIRELESS_WPA_DRIVER=wext
            ;;
        ipw2200|ipw2100)
            WIRELESS_WPA_DRIVER=wext
            ;;
        ndiswrapper|*.sys)
            WIRELESS_WPA_DRIVER=wext
            ;;
        rt2860*|rt2870*|r8187se)
            WIRELESS_WPA_DRIVER=wext
            ;;
        r8192*|r8712*|vt665*|wl)
            WIRELESS_WPA_DRIVER=wext
            ;;
        adm8211|at76*|ar9170*)
            WIRELESS_WPA_DRIVER=nl80211
            ;;
        ath5k|ath9k)
            WIRELESS_WPA_DRIVER=nl80211
            ;;
        b43|b43legacy|ssb)
            WIRELESS_WPA_DRIVER=nl80211
            ;;
        hostap_*)
            WIRELESS_WPA_DRIVER=nl80211
            ;;
        iwlagn|ipw3945)
            WIRELESS_WPA_DRIVER=nl80211
            ;;
        libertas*)
            WIRELESS_WPA_DRIVER=nl80211
            ;;
        mwl8k|p54pci|p54usb)
            WIRELESS_WPA_DRIVER=nl80211
            ;;
        rt2400pci|rt2500usb|rt2500pci)
            WIRELESS_WPA_DRIVER=nl80211
            ;;
        rt61pci|rt73usb|rtl818*)
            WIRELESS_WPA_DRIVER=nl80211
            ;;
        wl1251|wl1271|zd1211rw)
            WIRELESS_WPA_DRIVER=nl80211
            ;;
        *)
            WIRELESS_WPA_DRIVER=nl80211,wext
            ;;
    esac
fi
busybox ip link set "$WLAN_DEV" up
wpa_supplicant -i "$WLAN_DEV" -D "$WIRELESS_WPA_DRIVER" -c /etc/wpa_supplicant/wpa_supplicant.conf -B -P "/tmp/wpa_supplicant_$WLAN_DEV.pid"
sleep 5 # enough time for ethernet devices to appear
if ! wpa_cli status | grep wpa_state=COMPLETED ; then

    # can't run ifup now, it will be eventually called by wireless_ask_password
    rm -f -- "$hookdir/initqueue/ifup-$WLAN_DEV.sh"

    # run after any ethX
    /sbin/initqueue --name "zz-wireless_pw-$WLAN_DEV" --unique --onetime /sbin/wireless_ask_password_wrapper $WLAN_DEV
fi
