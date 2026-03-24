#!/bin/sh

command -v getarg > /dev/null || . /lib/dracut-lib.sh

if [ -z "$root" ] ; then
  root=saltboot
fi

# shellcheck disable=SC2034
rootok=1

# If we don't have a server, we need dhcp
if [ -z "$server" ] ; then
  # shellcheck disable=SC2034
  DHCPORSERVER="1"
fi;

# Saltboot prefix
prefix="rd.saltboot"

# Salt minion modifiers
MASTER="$(getarg "${prefix}.master=" -d -y "MASTER=")"
export MASTER
MINION_ID_PREFIX="$(getarg "${prefix}.id_prefix=" -d -y "MINION_ID_PREFIX=")"
export MINION_ID_PREFIX
SALT_DEVICE="$(getarg "${prefix}.salt_device=" -d -y "salt_device=")"
export SALT_DEVICE
SALT_TIMEOUT=$(getargnum 60 0 3600 "${prefix}.salt_timeout=" -d -y "SALT_TIMEOUT=")
export SALT_TIMEOUT
SALT_STOP_TIMEOUT=$(getargnum 15 0 3600 "${prefix}.salt_stop_timeout=" -d -y "SALT_STOP_TIMEOUT=")
export SALT_STOP_TIMEOUT
SALT_START_TIMEOUT=$(getargnum 10 0 3600 "${prefix}.salt_start_timeout=")
export SALT_START_TIMEOUT
SALT_KEY_TIMEOUT=$(getargnum 60 0 3600 "${prefix}.salt_key_timeout=")
export SALT_KEY_TIMEOUT

# Terminal naming modifiers
getargbool 0 "${prefix}.nosuffix" -d -y "DISABLE_UNIQUE_SUFFIX=" && DISABLE_UNIQUE_SUFFIX=1
export DISABLE_UNIQUE_SUFFIX
getargbool 0 "${prefix}.nohostname" -d -y "DISABLE_HOSTNAME_ID=" && DISABLE_HOSTNAME_ID=1
export DISABLE_HOSTNAME_ID
getargbool 0 "${prefix}.noprefix" -d -y "DISABLE_ID_PREFIX=" && DISABLE_ID_PREFIX=1
export DISABLE_ID_PREFIX
getargbool 0 "${prefix}.usefqdn" -d -y "USE_FQDN_MINION_ID=" && USE_FQDN_MINION_ID=1
export USE_FQDN_MINION_ID
getargbool 0 "${prefix}.usemac" -d -y "USE_MAC_MINION_ID=" && USE_MAC_MINION_ID=1
export USE_MAC_MINION_ID

# Debugging
getargbool 0 "${prefix}.debug" -d -y "kiwidebug=" && KIWIDEBUG=1
export KIWIDEBUG
