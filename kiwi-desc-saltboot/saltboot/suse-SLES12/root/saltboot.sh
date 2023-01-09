#!/bin/bash

if ! declare -f Echo > /dev/null ; then
  Echo() {
    echo "$@"
  }
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

rm /etc/machine-id
rm /var/lib/dbus/machine-id
dbus-uuidgen --ensure
systemd-machine-id-setup

salt_device=${salt_device:-$root}

if [ -f /usr/bin/venv-salt-minion ] ; then
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

mkdir -p $NEWROOT
if [ -n "$salt_device" ] && mount "$salt_device" $NEWROOT ; then
    for sd in $NEWROOT/etc/venv-salt-minion $NEWROOT/venv-salt-minion $NEWROOT/etc/salt $NEWROOT/salt $NEWROOT ; do
        if [ -f $sd/minion_id ] ; then # find valid salt configuration
            mkdir -p $INITRD_SALT_ETC
            cp -pr $sd/* $INITRD_SALT_ETC
            # remove activation key grain copied from the disk with the rest of configuration
            rm -f $INITRD_SALT_ETC/minion.d/kiwi_activation_key.conf
            #make sure we are not using venv config on normal minion
            rm -f /etc/salt/minion.d/00-venv.conf
            HAVE_MINION_ID=y
            break
        fi
    done
    umount $NEWROOT
fi

mkdir -p $INITRD_SALT_ETC/minion.d
cat > $INITRD_SALT_ETC/minion.d/grains-initrd.conf <<EOT
grains:
  saltboot_initrd: True
EOT

MACHINE_ID=`$INITRD_SALT_CALL --local --out newline_values_only grains.get machine_id`

# store machine id in grains permanently so it does not change when we switch to
# initrd and back
# this is not needed for SALT but SUSE Manager seems to rely on it
cat > $INITRD_SALT_ETC/minion.d/grains-machine_id.conf <<EOT
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
        SMBIOS_MANUFACTURER=`$INITRD_SALT_CALL --local --out newline_values_only smbios.get system-manufacturer | tr -d -c 'A-Za-z0-9_-'`
        SMBIOS_PRODUCT=`$INITRD_SALT_CALL --local --out newline_values_only smbios.get system-product-name | tr -d -c 'A-Za-z0-9_-'`
        SMBIOS_SERIAL=-`$INITRD_SALT_CALL --local --out newline_values_only smbios.get system-serial-number | tr -d -c 'A-Za-z0-9_-'`

        if [ "x$SMBIOS_SERIAL" == "x-None" ] ; then
            SMBIOS_SERIAL=
        fi

        # MINION_ID_PREFIX can be specified on kernel cmdline
        if [ -n "$MINION_ID_PREFIX" ] && [ -z "$DISABLE_ID_PREFIX" ] ; then
            echo "$MINION_ID_PREFIX.$SMBIOS_MANUFACTURER-$SMBIOS_PRODUCT$SMBIOS_SERIAL$UNIQUE_SUFFIX" > $INITRD_SALT_ETC/minion_id
        else
            echo "$SMBIOS_MANUFACTURER-$SMBIOS_PRODUCT$SMBIOS_SERIAL$UNIQUE_SUFFIX" > $INITRD_SALT_ETC/minion_id
        fi
    else

        # MINION_ID_PREFIX can be specified on kernel cmdline
        if [ -n "$MINION_ID_PREFIX" ] && [ -z "$DISABLE_ID_PREFIX" ] ; then
            echo "$MINION_ID_PREFIX.$HOSTNAME$UNIQUE_SUFFIX" > $INITRD_SALT_ETC/minion_id
        else
            echo "$HOSTNAME$UNIQUE_SUFFIX" > $INITRD_SALT_ETC/minion_id
        fi
    fi

    cat > $INITRD_SALT_ETC/minion.d/grains-minion_id_prefix.conf <<EOT
grains:
  minion_id_prefix: $MINION_ID_PREFIX
EOT
fi

if [ -n "$SALT_AUTOSIGN_GRAINS" ] ; then
    grains=
    agrains=
    IFS=, read -a grains_arr <<< "$SALT_AUTOSIGN_GRAINS"
    for g in "${grains_arr[@]}" ; do
        name=${g%%:*}
        agrains="$agrains    - $name"$'\n'
        if [[ $g == *:* ]]; then
            value=${g#*:}
            grains="$grains    $name: $value"$'\n'
        fi
    done
    cat > $INITRD_SALT_ETC/minion.d/autosign-grains-onetime.conf <<EOT
grains:
$grains

autosign_grains:
$agrains
EOT
fi

CUR_MASTER=`$INITRD_SALT_CALL --local --out newline_values_only grains.get master`
# do we have master explicitly configured?
if [ -z "$CUR_MASTER" -o "salt" == "$CUR_MASTER" ] ; then
    # either we have MASTER set on commandline
    # or we try to resolve the 'salt' alias
    if [ -z "$MASTER" ] ; then
        MASTER=`dig $DIG_OPTIONS -t CNAME salt.$DOMAIN | sed -e 's|;;.*||' -e 's|\.$||' `
    fi
fi

Echo "Using Salt master: ${MASTER:-$CUR_MASTER}"
echo "Using Salt master: ${MASTER:-$CUR_MASTER}" > /progress

if ! grep -q "^master: ${MASTER:-$CUR_MASTER}$" $INITRD_SALT_ETC/minion.d/susemanager.conf 2>/dev/null; then
    cat > $INITRD_SALT_ETC/minion.d/susemanager.conf <<EOT
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

if [ -z "$kiwidebug" ];then
    $INITRD_SALT_MINION -d
else
    $INITRD_SALT_MINION -d --log-file-level all
fi

sleep 1

SALT_PID=`cat /var/run/$INITRD_SALT_MINION.pid`

if [ -z "$SALT_PID" ] ; then
   systemException \
       "SALT Minion did not start" \
       "reboot"
fi

MINION_ID="`$INITRD_SALT_CALL --local --out newline_values_only grains.get id`"
MINION_FINGERPRINT="`$INITRD_SALT_CALL --local --out newline_values_only key.finger`"
while [ -z "$MINION_FINGERPRINT" ] ; do
  echo "Waiting for salt key..." > /progress
  Echo "Waiting for salt key..."
  sleep 1
  MINION_FINGERPRINT="`$INITRD_SALT_CALL --local --out newline_values_only key.finger`"
done

Echo
Echo "SALT Minion ID:"
Echo "$MINION_ID"
Echo
Echo "SALT Minion key fingerprint:"
Echo "$MINION_FINGERPRINT"
Echo

if [ -e /progress ] ; then
    # split line into two to fit to screen. Need tripple \ to properly pass through
    echo "Terminal ID: $MINION_ID\\\nFingerprint: $MINION_FINGERPRINT" > /progress
fi

SALT_TIMEOUT=${SALT_TIMEOUT:-60}
SALT_STOP_TIMEOUT=${SALT_STOP_TIMEOUT:-15}
SALT_STOP='/root/saltstop'
num=0
snum=0
while kill -0 "$SALT_PID" >/dev/null 2>&1; do
  sleep 1
  num=$(( num + 1 ))
  if [ "$num" == "$SALT_TIMEOUT" -a -n "$root" -a ! -f "$INITRD_SALT_CACHE/minion/extmods/states/saltboot.py" ] && \
     ! grep 'The Salt Master has cached the public key for this node' $INITRD_SALT_LOG && \
     mount $root $NEWROOT && [ -f $NEWROOT/etc/ImageVersion ]; then
    export systemIntegrity=fine
    export imageName=`cat $NEWROOT/etc/ImageVersion`
    echo "SUSE Manager server did not respond, trying local boot to\\\n$imageName" > /progress
    sleep 5
    kill "$SALT_PID"
    sleep 1
  fi
  #detect salt kill message
  if [ -f "$SALT_STOP" ];then
    snum=$(( snum + 1 ))
    if [ "$snum" -gt "$SALT_STOP_TIMEOUT" ];then
      kill -9 "$SALT_PID"
      rm "$SALT_STOP"
      sleep 1
    fi
  fi
done

if [ -f /salt_config ] ; then
  . /salt_config
fi

[ -n "$PROGRESS_PID" ] && kill $PROGRESS_PID
[ -n "$DC_PROGRESS_PID" ] && kill $DC_PROGRESS_PID

if [ "$systemIntegrity" = "unknown" ] ; then
   systemException \
       "SALT Minion did not create valid configuration" \
       "reboot"
fi

cat > $INITRD_SALT_ETC/minion.d/grains-initrd.conf <<EOT
grains:
  saltboot_initrd: False
EOT

rm -f $INITRD_SALT_ETC/minion.d/autosign-grains-onetime.conf

if test -e $NEWROOT/etc/venv-salt-minion ; then
    IMAGE_SALT_ETC=/etc/venv-salt-minion
else
    IMAGE_SALT_ETC=/etc/salt
fi

# copy salt, wicked and system configurations to deployed system
mkdir -p $NEWROOT/$IMAGE_SALT_ETC
cp -pr $INITRD_SALT_ETC/* $NEWROOT/$IMAGE_SALT_ETC
#make sure we are not using venv config on normal minion
rm -f $NEWROOT/etc/salt/minion.d/00-venv.conf

echo $MACHINE_ID > $NEWROOT/etc/machine-id

mkdir -p $NEWROOT/var/log/saltboot
num=1
while [ -e $NEWROOT/var/log/saltboot/saltboot_$num ] ; do
  num=$(( num + 1 ))
done
cp -pr $INITRD_SALT_LOG $NEWROOT/var/log/saltboot/saltboot_$num

if [ -n "$kernelAction" ] ; then
  # store image configuration over kexec
  cp /salt_config $NEWROOT/salt_config

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

# load image configuration stored over kexec
if [ -f $NEWROOT/salt_config ] ; then
  . $NEWROOT/salt_config
  rm -f $NEWROOT/salt_config
fi
