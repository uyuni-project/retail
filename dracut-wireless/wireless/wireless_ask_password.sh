#!/bin/bash

PATH=/usr/sbin:/usr/bin:/sbin:/bin

mkdir -p /etc/sysconfig/network/

# read wireless PSK from stdin
read PSK

wpa_cli disable 0
wpa_cli set_network 0 psk "\"$PSK\""
wpa_cli enable 0

try=0
while [ $try -lt 10 ]; do
    sleep 1
    if wpa_cli status | grep wpa_state=COMPLETED ; then
       # store verified PSK for wireless_update.sh
       echo "WIRELESS_WPA_PSK='$PSK'" >> "/tmp/wireless-$1"

       # setup the interface
       /sbin/ifup "$1"
       exit 0
    fi
    try=$(( try + 1 ))
done

# PSK didn't work, eventually try again
exit 1


