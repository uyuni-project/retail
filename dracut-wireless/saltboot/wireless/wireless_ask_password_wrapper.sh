#!/bin/bash

PATH=/usr/sbin:/usr/bin:/sbin:/bin

type getarg >/dev/null 2>&1 || . /lib/dracut-lib.sh
type ask_for_password >/dev/null 2>&1 || . /lib/dracut-crypt-lib.sh

WLAN_DEV=$1
cmd="/sbin/wireless_ask_password $WLAN_DEV"
ask_for_password --cmd "$cmd" --prompt 'WIRELESS WPA PSK'

