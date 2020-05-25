#!/bin/bash

if ! declare -f Echo > /dev/null ; then
  Echo() {
    echo "$@"
  }
fi

if ! [ -s /etc/resolv.conf ] ; then
    Echo "No network, skipping saltboot..."
    exit 0
fi

IFCONFIG="$(compgen -G '/tmp/leaseinfo.*.dhcp.ipv*')"
if [ -f "$IFCONFIG" ]; then
    . "$IFCONFIG"
else
    Echo "No network details available, skipping saltboot";
    exit 0
fi

NEWROOT=${NEWROOT:-/mnt}
export NEWROOT

if [ -e /usr/bin/plymouth ] ; then
    mkfifo /progress
    bash -c 'while true ; do read msg < /progress ; plymouth message --text="$msg" ; done ' &
    PROGRESS_PID=$!
else
    mkfifo /progress
    bash -c 'while true ; do read msg < /progress ; echo -n -e "\033[2K$msg\015" >/dev/console ; done ' &
    PROGRESS_PID=$!
fi

echo -n > /dc_progress
bash -c 'tail -f /dc_progress | while true ; do read msg ; echo "$msg" >/progress ; done ' &
DC_PROGRESS_PID=$!

rm -f /etc/machine-id
mkdir -p /var/lib/dbus
rm -f /var/lib/dbus/machine-id
dbus-uuidgen --ensure
systemd-machine-id-setup

# make sure there are no pending changes in devices
udevadm settle -t 60

# This should be visible after pressing ESC
Echo "Available disk devices" >&2
Echo "ls -l /dev/disk/by-id" >&2
ls -l /dev/disk/by-id >&2
Echo "ls -l /dev/disk/by-path" >&2
ls -l /dev/disk/by-path >&2

salt_device=${salt_device:-${root#block:}}

mkdir -p $NEWROOT
if [ -n "$salt_device" ] && mount "$salt_device" $NEWROOT ; then
    for sd in $NEWROOT/etc/salt $NEWROOT/salt $NEWROOT ; do
        if [ -f $sd/minion_id ] ; then # find valid salt configuration
            mkdir -p /etc/salt
            cp -pr $sd/* /etc/salt
            # remove activation key grain copied from the disk with the rest of configuration
            rm -f /etc/salt/minion.d/kiwi_activation_key.conf
            HAVE_MINION_ID=y
            break
        fi
    done
    umount $NEWROOT
fi

mkdir -p /etc/salt/minion.d
cat > /etc/salt/minion.d/grains-initrd.conf <<EOT
grains:
  saltboot_initrd: True
EOT

MACHINE_ID=`salt-call --local --out newline_values_only grains.get machine_id`

# store machine id in grains permanently so it does not change when we switch to
# initrd and back
# this is not needed for SALT but SUSE Manager seems to rely on it
cat > /etc/salt/minion.d/grains-machine_id.conf <<EOT
grains:
  machine_id: $MACHINE_ID
EOT

echo $MACHINE_ID > /etc/machine-id

DIG_OPTIONS="+short"
if dig -h | grep -q '\[no\]cookie'; then
    DIG_OPTIONS="+nocookie +short"
fi

if [ -z "$HAVE_MINION_ID" ] ; then
    FQDN=`dig $DIG_OPTIONS -x "${IPADDR%/*}" | sed -e 's|;;.*||' -e 's|\.$||' `
    if [ -n "$USE_FQDN_MINION_ID" ]; then
        HOSTNAME="$FQDN"
    else
        HOSTNAME=${FQDN%%.*}
    fi

    if [ -n "$DISABLE_UNIQUE_SUFFIX" ] ; then
        UNIQUE_SUFFIX=
    else
        UNIQUE_SUFFIX="-${MACHINE_ID:0:4}"
    fi

    if [ -z "$HOSTNAME" ] || [ -n "$DISABLE_HOSTNAME_ID" ]; then
        SMBIOS_MANUFACTURER=`salt-call --local --out newline_values_only smbios.get system-manufacturer | tr -d -c 'A-Za-z0-9_-'`
        SMBIOS_PRODUCT=`salt-call --local --out newline_values_only smbios.get system-product-name | tr -d -c 'A-Za-z0-9_-'`
        SMBIOS_SERIAL=-`salt-call --local --out newline_values_only smbios.get system-serial-number | tr -d -c 'A-Za-z0-9_-'`

        if [ "x$SMBIOS_SERIAL" == "x-None" ] ; then
            SMBIOS_SERIAL=
        fi

        # MINION_ID_PREFIX can be specified on kernel cmdline
        if [ -n "$MINION_ID_PREFIX" ] && [ -z "$DISABLE_ID_PREFIX" ] ; then
            echo "$MINION_ID_PREFIX.$SMBIOS_MANUFACTURER-$SMBIOS_PRODUCT$SMBIOS_SERIAL$UNIQUE_SUFFIX" > /etc/salt/minion_id
        else
            echo "$SMBIOS_MANUFACTURER-$SMBIOS_PRODUCT$SMBIOS_SERIAL$UNIQUE_SUFFIX" > /etc/salt/minion_id
        fi
    else

        # MINION_ID_PREFIX can be specified on kernel cmdline
        if [ -n "$MINION_ID_PREFIX" ] && [ -z "$DISABLE_ID_PREFIX" ] ; then
            echo "$MINION_ID_PREFIX.$HOSTNAME$UNIQUE_SUFFIX" > /etc/salt/minion_id
        else
            echo "$HOSTNAME$UNIQUE_SUFFIX" > /etc/salt/minion_id
        fi
    fi

    cat > /etc/salt/minion.d/grains-minion_id_prefix.conf <<EOT
grains:
  minion_id_prefix: $MINION_ID_PREFIX
EOT
fi

# send basic grains in the minion start event. This allows salt master to work with saltboot minion
# with 1 (new registration) or 0 (already existing registration) grains calls
cat > /etc/salt/minion.d/grains-startup-event.conf <<EOT
start_event_grains:
  - machine_id
  - saltboot_initrd
  - susemanager
EOT

CUR_MASTER=`salt-call --local --out newline_values_only grains.get master`
# do we have master explicitly configured?
if [ -z "$CUR_MASTER" -o "salt" == "$CUR_MASTER" ] ; then
    # either we have MASTER set on commandline
    # or we try to resolve the 'salt' alias
    if [ -z "$MASTER" ] ; then
        MASTER=`dig $DIG_OPTIONS -t CNAME salt.$DNSDOMAIN | sed -e 's|;;.*||' -e 's|\.$||' `
    fi
    if [ -n "$MASTER" ] ; then
        echo "master: $MASTER" > /etc/salt/minion.d/master.conf
    fi
    # else
    # ... if it fails, do nothing and let it fall back to 'salt'
    # by continuing we hide dns errors. Shouldn't we require proper setup?
fi

Echo "Using Salt master: ${MASTER:-$CUR_MASTER}"
echo "Using Salt master: ${MASTER:-$CUR_MASTER}" > /progress

if [ -z "$kiwidebug" ];then
    salt-minion -d
else
    salt-minion -d --log-file-level all
fi

sleep 1

SALT_PID=`cat /var/run/salt-minion.pid`

if [ -z "$SALT_PID" ] ; then
    Echo "Salt Minion did not start"
    echo "Salt Minion did not start" > /progress
    sleep 10
    reboot -f
fi

MINION_ID="`salt-call --local --out newline_values_only grains.get id`"
MINION_FINGERPRINT="`salt-call --local --out newline_values_only key.finger`"
while [ -z "$MINION_FINGERPRINT" ] ; do
  echo "Waiting for salt key..." > /progress
  Echo "Waiting for salt key..."
  sleep 1
  MINION_FINGERPRINT="`salt-call --local --out newline_values_only key.finger`"
done

Echo
Echo "SALT Minion ID:"
Echo "$MINION_ID"
Echo
Echo "SALT Minion key fingerprint:"
Echo "$MINION_FINGERPRINT"
Echo

# split line into two to fit to screen. Need triple \ to properly pass through
echo "Terminal ID: $MINION_ID\\\nFingerprint: $MINION_FINGERPRINT" > /progress

SALT_TIMEOUT=${SALT_TIMEOUT:-60}
num=0
while kill -0 "$SALT_PID" >/dev/null 2>&1; do
  sleep 1
  num=$(( num + 1 ))
  if [ "$num" == "$SALT_TIMEOUT" -a -n "$root" -a ! -f '/var/cache/salt/minion/extmods/states/saltboot.py' ] && \
     ! grep 'The Salt Master has cached the public key for this node' /var/log/salt/minion && \
     mount ${root#block:} $NEWROOT && [ -f $NEWROOT/etc/ImageVersion ]; then
    export systemIntegrity=fine
    export imageName=`cat $NEWROOT/etc/ImageVersion`
    echo "SUSE Manager server does not respond, trying local boot to\\\n$imageName" > /progress
    Echo "SUSE Manager server does not respond, trying local boot to\\\n$imageName"
    sleep 5
    kill "$SALT_PID"
    sleep 1
  fi
done

if [ -f /salt_config ] ; then
  . /salt_config
fi

[ -n "$PROGRESS_PID" ] && kill $PROGRESS_PID
[ -n "$DC_PROGRESS_PID" ] && kill $DC_PROGRESS_PID

if [ "$systemIntegrity" = "unknown" ] ; then
    Echo "SALT Minion did not create valid configuration"
    sleep 10
    reboot -f
fi

cat > /etc/salt/minion.d/grains-initrd.conf <<EOT
grains:
  saltboot_initrd: False
EOT

cp -pr /etc/salt $NEWROOT/etc
echo $MACHINE_ID > $NEWROOT/etc/machine-id

mkdir -p $NEWROOT/var/log/salt
num=1
while [ -e $NEWROOT/var/log/salt/saltboot_$num ] ; do
  num=$(( num + 1 ))
done
cp -pr /var/log/salt $NEWROOT/var/log/salt/saltboot_$num

if [ -n "$kernelAction" ] ; then
  umount -a
  sync
  if [ "$kernelAction" = "reboot" ] ; then
    Echo "Reboot with correct kernel version"
    sleep 10
    reboot -f
  elif [ "$kernelAction" = "kexec" ] ; then
    kexec -e
    Echo "Kexec failed, reboot with correct kernel version"
    sleep 10
    reboot -f
  fi
fi
