#!/bin/bash

# Default variables
PROGRESS="/progress"
DIG_OPTIONS=(+short)
dig -h | grep -q '\[no\]cookie' && DIG_OPTIONS=("${DIG_OPTIONS[@]}" +nocookie +short)

is_plymouth_available() {
	[ -e /usr/bin/plymouth ]
}

read_progress() {
	sleep 1
	if is_plymouth_available; then
		while true; do
			#shellcheck disable=SC2162
			if ! read msg <"$PROGRESS"; then
				continue
			fi
			plymouth message --text="$msg"
		done
	else
		while true; do
			#shellcheck disable=SC2162
			if ! read msg <"$PROGRESS"; then
				continue
			fi
			echo -n -e "\033[2K$msg\015" >/dev/console
		done
	fi
}

read_dc_progress() {
	sleep 1
	echo -n >/dc_progress
	#shellcheck disable=SC2162
	exec tail -f /dc_progress | while true; do
		read msg
		echo "$msg" >"$PROGRESS"
	done
}

setup_progress_pipes() {
	if [ -e "$PROGRESS" ] && ! [ -p "$PROGRESS" ]; then
		rm -f -- "$PROGRESS"
	fi
	if ! [ -p "$PROGRESS" ]; then
		mkfifo -- "$PROGRESS"
	fi
	read_progress &
	PROGRESS_PID=$!

	read_dc_progress &
	DC_PROGRESS_PID=$!
}

cleanup() {
	[ -n "$PROGRESS_PID" ] && kill "$PROGRESS_PID" 2>/dev/null
	[ -n "$DC_PROGRESS_PID" ] && kill "$DC_PROGRESS_PID" 2>/dev/null
}

Echo() {
	echo "$@"
	echo "$@" >"$PROGRESS"
}

wait_for_network() {
	NET_TIMEOUT=30
	while [ $NET_TIMEOUT -gt 0 ]; do
		IFCONFIG="$(compgen -G '/tmp/leaseinfo.*.dhcp.ipv*' | xargs grep -l BOOTFILE | head -1)"
		if [ ! -f "$IFCONFIG" ]; then
			IFCONFIG="$(compgen -G '/tmp/leaseinfo.*.dhcp.ipv*' | head -1)"
		fi
		if [ -s /etc/resolv.conf ] && [ -f "$IFCONFIG" ]; then
			break
		fi
		Echo "Waiting for network to setup (${NET_TIMEOUT}s)"
		NET_TIMEOUT=$((NET_TIMEOUT - 1))
		sleep 1
	done

	if [ -f "$IFCONFIG" ] && [ -s /etc/resolv.conf ]; then
		# shellcheck disable=SC1090
		. "$IFCONFIG"
	else
		Echo "No network available, aborting saltboot"
		exit 0
	fi
}

is_venv_salt_call_installed() {
	[ -f /usr/bin/venv-salt-call ]
}

configure_salt_vars() {
	if is_venv_salt_call_installed; then
		INITRD_SALT_ETC=/etc/venv-salt-minion
		INITRD_SALT_LOG=/var/log/venv-salt-minion.log
		INITRD_SALT_CALL=venv-salt-call
		INITRD_SALT_MINION=venv-salt-minion
		INITRD_SALT_CACHE=/var/cache/venv-salt-minion
	else
		INITRD_SALT_ETC=/etc/salt
		INITRD_SALT_LOG=/var/log/salt/minion
		INITRD_SALT_CALL=salt-call
		INITRD_SALT_MINION=salt-minion
		INITRD_SALT_CACHE=/var/cache/salt
	fi
}

load_existing_salt_config() {
	if [ -n "$SALT_DEVICE" ] && mount "$SALT_DEVICE" "$NEWROOT"; then
		for sd in "${NEWROOT}/etc/venv-salt-minion" "${NEWROOT}/venv-salt-minion" "${NEWROOT}/etc/salt" "${NEWROOT}/salt" "$NEWROOT"; do
			if [ -f "${sd}/minion_id" ]; then # find valid salt configuration
				mkdir -p "$INITRD_SALT_ETC"
				cp -pr "$sd"/* "$INITRD_SALT_ETC"
				# remove activation key grain copied from the disk with the rest of configuration
				rm -f "${INITRD_SALT_ETC}/minion.d/kiwi_activation_key.conf"
				#make sure we are not using venv config on normal minion
				rm -f /etc/salt/minion.d/00-venv.conf
				HAVE_MINION_ID=y
				break
			fi
		done
		umount "$NEWROOT"
	fi
}

fetch_terminal_defaults() {
	curl -s "http://${MASTER:-$BOOTSERVERADDR}/saltboot/defaults" >/tmp/defaults
	if [ ! -s /tmp/defaults ]; then
		curl -s "tftp://${MASTER:-$BOOTSERVERADDR}/defaults" >/tmp/defaults
	fi

	if [ -s /tmp/defaults ]; then
		while IFS='=' read -r key value; do
			case "$key" in
			MINION_ID_PREFIX | DISABLE_ID_PREFIX | DISABLE_UNIQUE_SUFFIX | DEFAULT_KERNEL_PARAMETERS | USE_FQDN_MINION_ID | DISABLE_HOSTNAME_ID)
				# Only assign if current value is empty
				if [ -z "${!key}" ]; then
					printf -v "$key" '%s' "$value"
				fi
				;;
			esac
		done </tmp/defaults
		# saltboot state looks for if we have DEFAULT_KERNEL_PARAMETERS envvar
		export DEFAULT_KERNEL_PARAMETERS
	fi
}

generate_minion_id() {
	MINION_ID=""
	if [ -n "$USE_MAC_MINION_ID" ]; then
		# ip output has multiple hw addressed, we need the one beginning with ether
		# first grep gets `ether MAC`, second one extracts MAC.
		MAC_MASK="..:..:..:..:..:.."
		MINION_ID=$(ip addr show dev "$INTERFACE" | grep -o -E "ether $MAC_MASK" | grep -o -E "$MAC_MASK")
		if [ -z "$MINION_ID" ]; then
			Echo "Unable to get MAC based minion id."
			sleep 5
		fi
	fi

	if [ -z "$MINION_ID" ] && [ -z "$DISABLE_HOSTNAME_ID" ]; then
		FQDN=$(dig "${DIG_OPTIONS[@]}" -x "${IPADDR%/*}" | sed -e 's|;;.*||' -e 's|\.$||')
		if [ -n "$USE_FQDN_MINION_ID" ]; then
			MINION_ID="$FQDN"
		else
			MINION_ID="${FQDN%%.*}"
		fi
	fi

	if [ -z "$MINION_ID" ]; then
		SMBIOS_MANUFACTURER=$($INITRD_SALT_CALL --local --out newline_values_only smbios.get system-manufacturer | tr -d -c 'A-Za-z0-9_-')
		SMBIOS_PRODUCT=$($INITRD_SALT_CALL --local --out newline_values_only smbios.get system-product-name | tr -d -c 'A-Za-z0-9_-')
		SMBIOS_SERIAL=$($INITRD_SALT_CALL --local --out newline_values_only smbios.get system-serial-number | tr -d -c 'A-Za-z0-9_-')

		[ "$SMBIOS_SERIAL" == "None" ] && SMBIOS_SERIAL=""

		MINION_ID="${SMBIOS_MANUFACTURER}-${SMBIOS_PRODUCT}${SMBIOS_SERIAL:+-${SMBIOS_SERIAL}}"
	fi

	UNIQUE_SUFFIX=""
	if [ -z "$DISABLE_UNIQUE_SUFFIX" ]; then
		UNIQUE_SUFFIX="-${MACHINE_ID:0:4}"
	fi

	# MINION_ID_PREFIX is mandatory
	if [ -z "$MINION_ID_PREFIX" ]; then
		Echo "Missing MINION_ID_PREFIX value. Check branch server configuration. Rebooting..."
		sleep 10
		reboot -f
	fi

	if [ -z "$DISABLE_ID_PREFIX" ]; then
		BRANCH_ID_PREFIX="${MINION_ID_PREFIX}."
	else
		BRANCH_ID_PREFIX=""
	fi

	echo "${BRANCH_ID_PREFIX}${MINION_ID}${UNIQUE_SUFFIX}" >$INITRD_SALT_ETC/minion_id

	cat >$INITRD_SALT_ETC/minion.d/grains-minion_id_prefix.conf <<EOT
grains:
  minion_id_prefix: $MINION_ID_PREFIX
EOT
}

prepare_autosigned_grains() {
	if [ -n "$SALT_AUTOSIGN_GRAINS" ]; then
		Echo "Storing auto-sign grain"
		grains=
		agrains=
		readarray -d , -t grains_arr <<<"$SALT_AUTOSIGN_GRAINS"
		for g in "${grains_arr[@]}"; do
			name=${g%%:*}
			agrains="$agrains    - $name"$'\n'
			if [[ $g == *:* ]]; then
				value=${g#*:}
				grains="$grains    $name: $value"$'\n'
			fi
		done
		cat >$INITRD_SALT_ETC/minion.d/autosign-grains-onetime.conf <<EOT
grains:
$grains

autosign_grains:
$agrains
EOT
	fi
}

prepare_salt_config() {
	CUR_MASTER=$($INITRD_SALT_CALL --local --out newline_values_only grains.get master)
	# do we have master explicitly configured?
	if [ -z "$CUR_MASTER" ] || [ "salt" == "$CUR_MASTER" ]; then
		# either we have MASTER set on commandline
		# or we try to resolve the 'salt' alias
		if [ -z "$MASTER" ]; then
			MASTER=$(dig "${DIG_OPTIONS[@]}" -t CNAME "salt.$DNSDOMAIN" | sed -e 's|;;.*||' -e 's|\.$||')
		fi
	fi

	Echo "Using Salt master: ${MASTER:-$CUR_MASTER}"

	if ! grep -Fqx "master: ${MASTER:-$CUR_MASTER}$" "${INITRD_SALT_ETC}/minion.d/susemanager.conf" 2>/dev/null; then
		cat >$INITRD_SALT_ETC/minion.d/susemanager.conf <<EOT
# This file was generated by saltboot
master: ${MASTER:-$CUR_MASTER}

server_id_use_crc: adler32
enable_legacy_startup_events: False
enable_fqdns_grains: False

start_event_grains:
  - machine_id
  - saltboot_initrd
  - susemanager

# Define SALT_RUNNING env variable for pkg modules
system-environment:
  modules:
    pkg:
      _:
        SALT_RUNNING: 1
EOT
		rm -f $INITRD_SALT_ETC/minion.d/master.conf
		rm -f $INITRD_SALT_ETC/minion.d/grains-startup-event.conf
	fi
}

start_and_wait_for_minion() {
	if [ -z "$KIWIDEBUG" ]; then
		$INITRD_SALT_MINION -d
	else
		$INITRD_SALT_MINION -d --log-file-level all
	fi

	SALT_START_TIMEOUT=${SALT_START_TIMEOUT:-10}
	while [ ! -s "/var/run/$INITRD_SALT_MINION.pid" ] && [ "$SALT_START_TIMEOUT" -gt 0 ]; do
		Echo "Waiting for minion to start ... (${SALT_START_TIMEOUT}s)"
		sleep 1
		SALT_START_TIMEOUT=$((SALT_START_TIMEOUT - 1))
	done

	SALT_PID=$(cat "/var/run/$INITRD_SALT_MINION.pid" 2>/dev/null)

	if [ -z "$SALT_PID" ]; then
		Echo "Salt Minion did not start, rebooting in 10s"
		sleep 10
		reboot -f
	fi
}

main() {
	trap cleanup EXIT

	NEWROOT="${NEWROOT:-/mnt}"
	export NEWROOT
	mkdir -p "$NEWROOT"
	SALT_DEVICE="${SALT_DEVICE:-${root#block:}}"

	setup_progress_pipes
	wait_for_network

	Echo "Preparing saltboot environment"

	rm -f /etc/machine-id
	mkdir -p /var/lib/dbus
	rm -f /var/lib/dbus/machine-id
	dbus-uuidgen --ensure
	systemd-machine-id-setup

	# make sure there are no pending changes in devices
	udevadm settle -t 60

	# from now on, disable automatic RAID assembly
	udevproperty rd_NO_MD=1

	# This should be visible after pressing ESC
	echo "Available disk devices" >&2
	echo "ls -l /dev/disk/by-id" >&2
	ls -l /dev/disk/by-id >&2
	echo "ls -l /dev/disk/by-path" >&2
	ls -l /dev/disk/by-path >&2

	configure_salt_vars
	load_existing_salt_config

	# set we are in the initrd environment. Saltboot state will refuse to start without this.
	mkdir -p "${INITRD_SALT_ETC}/minion.d"
	cat >"${INITRD_SALT_ETC}/minion.d/grains-initrd.conf" <<EOT
grains:
  saltboot_initrd: True
EOT

	# store machine id in grains permanently so it does not change when we switch to initrd and back
	# this is not needed for SALT but SMLM relies on it
	MACHINE_ID="$("$INITRD_SALT_CALL" --local --out newline_values_only grains.get machine_id)"
	cat >"$INITRD_SALT_ETC/minion.d/grains-machine_id.conf" <<EOT
grains:
  machine_id: $MACHINE_ID
EOT
	echo "$MACHINE_ID" >/etc/machine-id

	if [ -z "$HAVE_MINION_ID" ]; then
		fetch_terminal_defaults
		generate_minion_id
	fi
	prepare_salt_config
	prepare_autosigned_grains
	start_and_wait_for_minion

	# reload minion id from what salt actually knows
	MINION_ID="$($INITRD_SALT_CALL --local --out newline_values_only grains.get id)"
	MINION_FINGERPRINT="$($INITRD_SALT_CALL --local --out newline_values_only key.finger)"

	SALT_KEY_TIMEOUT=${SALT_KEY_TIMEOUT:-60}
	while [ -z "$MINION_FINGERPRINT" ] && [ "$SALT_KEY_TIMEOUT" -gt 0 ]; do
		Echo "Waiting for salt key... (${SALT_KEY_TIMEOUT}s)"
		sleep 1
		MINION_FINGERPRINT="$($INITRD_SALT_CALL --local --out newline_values_only key.finger)"
		SALT_KEY_TIMEOUT=$((SALT_KEY_TIMEOUT - 1))
	done

	if [ -z "$MINION_FINGERPRINT" ]; then
		Echo "Cannot obtain salt key, rebooting in 10s"
		sleep 10
		reboot -f
	fi

	echo
	echo "SALT Minion ID:"
	echo "$MINION_ID"
	echo
	echo "SALT Minion key fingerprint:"
	echo "$MINION_FINGERPRINT"
	echo

	# split line into two to fit to screen. Need triple \ to properly pass through
	Echo "Terminal ID: $MINION_ID\\\nFingerprint: $MINION_FINGERPRINT"

	SALT_STOP_TIMEOUT=${SALT_STOP_TIMEOUT:-15}
	SALT_STOP='/root/saltstop'
	num=0
	snum=0
	while kill -0 "$SALT_PID" >/dev/null 2>&1; do
		sleep 1
		num=$((num + 1))
		if [ "$num" == "$SALT_TIMEOUT" ] && [ -n "$root" ] && [ ! -f "$INITRD_SALT_CACHE/minion/extmods/states/saltboot.py" ] &&
			! grep 'The Salt Master has cached the public key for this node' "$INITRD_SALT_LOG" &&
			mount "${root#block:}" "$NEWROOT" && [ -f "${NEWROOT}/etc/ImageVersion" ]; then
			systemIntegrity=fine
			imageName=$(cat "${NEWROOT}/etc/ImageVersion")
			Echo "Salt master did not respond, trying local boot to '$imageName'"
			sleep 5
			kill "$SALT_PID"
			sleep 1
		fi
		#detect salt kill message
		if [ -f "$SALT_STOP" ]; then
			snum=$((snum + 1))
			if [ "$snum" -gt "$SALT_STOP_TIMEOUT" ]; then
				kill -9 "$SALT_PID"
				rm "$SALT_STOP"
				sleep 1
			fi
		fi
	done

	# load config status report from the saltboot state
	if [ -f /salt_config ]; then
		#shellcheck disable=SC1091
		. /salt_config
	fi

	if [ "$systemIntegrity" = "unknown" ]; then
		Echo "Salt minion did not create valid configuration, rebooting in 10s"
		sleep 10
		reboot -f
	fi

	# mark we are no longer in initrd
	cat >"${INITRD_SALT_ETC}/minion.d/grains-initrd.conf" <<EOT
grains:
  saltboot_initrd: False
EOT

	# cleanup auto sign grains so that they are not preserved in the system
	rm -f "${INITRD_SALT_ETC}/minion.d/autosign-grains-onetime.conf"

	if [ -e "${NEWROOT}/etc/venv-salt-minion" ]; then
		IMAGE_SALT_ETC=/etc/venv-salt-minion
	else
		IMAGE_SALT_ETC=/etc/salt
	fi

	# copy salt, wicked and system configurations to deployed system
	mkdir -p "${NEWROOT}/$IMAGE_SALT_ETC"
	cp -pr "$INITRD_SALT_ETC"/* "${NEWROOT}/$IMAGE_SALT_ETC"
	#make sure we are not using venv config on normal minion
	rm -f "${NEWROOT}/etc/salt/minion.d/00-venv.conf"

	echo "$MACHINE_ID" >"${NEWROOT}/etc/machine-id"

	# preserve wicked lease so that we don't end up with another new IP address
	mkdir -p "${NEWROOT}/var/lib/wicked"
	cp /var/lib/wicked/lease* "${NEWROOT}/var/lib/wicked/"

	# copy salt log files
	mkdir -p "${NEWROOT}/var/log/saltboot"
	num=1
	while [ -e "${NEWROOT}/var/log/saltboot/saltboot_$num" ]; do
		num=$((num + 1))
	done
	cp -pr "$INITRD_SALT_LOG" "${NEWROOT}/var/log/saltboot/saltboot_$num"

	if [ -n "$kernelAction" ]; then
		umount -a
		sync
		if [ "$kernelAction" = "reboot" ]; then
			Echo "Reboot with correct kernel version in 10s"
			sleep 10
			reboot -f
		elif [ "$kernelAction" = "kexec" ]; then
			kexec -e
			Echo "Kexec failed, reboot with correct kernel version in 10s"
			sleep 10
			reboot -f
		fi
	fi
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
	main "$@"
fi
