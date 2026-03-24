#!/bin/sh

if [ -z "$root" ] ; then
  root=saltboot
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
export SALT_STOP_TIMEOUT=$(getarg SALT_STOP_TIMEOUT=)
export SALT_DEVICE=$(getarg salt_device=)
export SALT_START_TIMEOUT=$(getarg rd.saltboot.salt_start_timeout=)
export SALT_KEY_TIMEOUT=$(getarg rd.saltboot.salt_key_timeout=)

# Terminal naming modifiers
export DISABLE_UNIQUE_SUFFIX=$(getarg DISABLE_UNIQUE_SUFFIX=)
export DISABLE_HOSTNAME_ID=$(getarg DISABLE_HOSTNAME_ID=)
export DISABLE_ID_PREFIX=$(getarg DISABLE_ID_PREFIX=)
export USE_FQDN_MINION_ID=$(getarg USE_FQDN_MINION_ID=)
export USE_MAC_MINION_ID=$(getarg USE_MAC_MINION_ID=)

# Debugging
export KIWIDEBUG=$(getarg kiwidebug=)
