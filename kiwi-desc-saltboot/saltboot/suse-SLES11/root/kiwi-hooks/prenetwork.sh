
# setup wlan

WLAN_DEV=`hwinfo --wlan | grep "Device File:" |sed -e "s|.*Device File: *||" |head -n 1`

if [ -n "$WLAN_DEV" ]; then
	if [ -n "$WIRELESS_WPA_PSK" -a -n "$WIRELESS_ESSID" ]; then
		#try to write wpa configuration using cmdline args
		echo "ctrl_interface=/var/run/wpa_supplicant"         > /etc/wpa_supplicant/wpa_supplicant.conf
		echo "ctrl_interface_group=wheel"                    >> /etc/wpa_supplicant/wpa_supplicant.conf
		wpa_passphrase "$WIRELESS_ESSID" "$WIRELESS_WPA_PSK" >>/etc/wpa_supplicant/wpa_supplicant.conf
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
	wpa_supplicant -i "$WLAN_DEV" -D "$WIRELESS_WPA_DRIVER" -c /etc/wpa_supplicant/wpa_supplicant.conf -B
fi
