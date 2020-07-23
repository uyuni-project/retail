#!/bin/sh

if [ -z "$root" ] ; then
  root=saltboot
else
  # we have root, we can eventually continue without network after timeout

  # we however need to check if the root is valid. If we are still waiting
  # for the device, then lets keep waiting and end in emergency shell

  # the timeout is controlled by rd.retry option

  local _name
  _name="$(str_replace "${root#block:}" '/' '\x2f')"
  cat <<EOF_TIMEOUT > "$hookdir/initqueue/timeout/saltboot-timeout.sh"
for f in wait-network.sh "devexists-$_name.sh"; do
  if [ ! -e "$hookdir/initqueue/finished/\$f" ] || ( . "$hookdir/initqueue/finished/\$f" ); then
    rm -f -- "$hookdir/initqueue/finished/wait-network.sh"
    rm -f -- "$hookdir/initqueue/finished/devexists-$_name.sh"
  fi
done
EOF_TIMEOUT

fi

rootok=1

# If we don't have a server, we need dhcp
if [ -z "$server" ] ; then
    DHCPORSERVER="1"
fi;

# Salt minion modifiers
export MASTER=$(getarg MASTER=)
export MINION_ID_PREFIX=$(getarg MINION_ID_PREFIX=)
export SALT_TIMEOUT=$(getarg SALT_TIMEOUT=)
export salt_device=$(getarg salt_device=)
export SALTBOOT_MODE=$(getarg SALTBOOT_MODE=)

# Terminal naming modifiers
export DISABLE_UNIQUE_SUFFIX=$(getarg DISABLE_UNIQUE_SUFFIX=)
export DISABLE_HOSTNAME_ID=$(getarg DISABLE_HOSTNAME_ID=)
export DISABLE_ID_PREFIX=$(getarg DISABLE_ID_PREFIX=)
export USE_FQDN_MINION_ID=$(getarg USE_FQDN_MINION_ID=)

# YOMI compatible naming - disable all saltboot namings and use just FQDN, unless specified otherwise
if [ "$SALTBOOT_MODE" = "yomi" ]; then
  if [ -z "$DISABLE_UNIQUE_SUFFIX" ]; then
    export DISABLE_UNIQUE_SUFFIX=1
  fi
  if [ -z "$DISABLE_ID_PREFIX" ]; then
    export DISABLE_ID_PREFIX=1
  fi
  if [ -z "$USE_FQDN_MINION_ID" ]; then
    export USE_FQDN_MINION_ID=1
  fi
fi

# Debugging
export kiwidebug=$(getarg kiwidebug=)
