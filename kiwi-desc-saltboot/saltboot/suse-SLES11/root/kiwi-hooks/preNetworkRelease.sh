function appendWirelessPXENetwork
{
	local prefix=$1
	if [ "$WLAN_DEV" == "$PXE_IFACE" ]; then
		#append wireless configuration to sysconfig file
		local niface=$prefix/etc/sysconfig/network/ifcfg-$PXE_IFACE
		if [ -f "$niface" ] && ! grep -q "^WIRELESS" "$niface" ; then
			echo "WIRELESS='yes'" >> "$niface"
			echo "WIRELESS_WPA_DRIVER='$WIRELESS_WPA_DRIVER'" >> "$niface"
			if [ -n "$WIRELESS_WPA_PSK" -a -n "$WIRELESS_ESSID" ]; then
				# use creds from cmdline
				echo "WIRELESS_ESSID='$WIRELESS_ESSID'" >> "$niface"
				echo "WIRELESS_WPA_PSK='$WIRELESS_WPA_PSK'" >> "$niface"
				echo "WIRELESS_AUTH_MODE='psk'" >> "$niface"
			else
				#use custom wpa_supplicant.conf
				mkdir -p $prefix/etc/wpa_supplicant/
				cp -f /etc/wpa_supplicant/wpa_supplicant.conf $prefix/etc/wpa_supplicant/wpa_supplicant.conf
				echo "WIRELESS_WPA_CONF='/etc/wpa_supplicant/wpa_supplicant.conf'" >> "$niface"
			fi
		fi
	fi
}

if [ $LOCAL_BOOT = "no" ] && [ $systemIntegrity = "clean" ];then
	setupDefaultPXENetwork /mnt
fi

if [ -n "$WLAN_DEV" ]; then
	#stop wpa_supplicant
	killall wpa_supplicant

	appendWirelessPXENetwork /mnt
fi
