#!/bin/sh

command -v getarg > /dev/null || . /lib/dracut-lib.sh

if [ -z "$root" ] ; then
  root=saltboot
fi

rootok=1

# If we don't have a server, we need dhcp
if [ -z "$server" ] ; then
  DHCPORSERVER="1"
fi;

# Saltboot prefix
_prefix="rd.saltboot"

# Salt minion modifiers
MASTER=$(getarg "${_prefix}.master=" -d -y "MASTER=")
export MASTER

MINION_ID_PREFIX=$(getarg "${_prefix}.id_prefix=" -d -y "MINION_ID_PREFIX=")
export MINION_ID_PREFIX

SALT_TIMEOUT=$(getargnum 60 10 3600 "${_prefix}.timeout=" -d -y "SALT_TIMEOUT=")
export SALT_TIMEOUT

SALT_STOP_TIMEOUT=$(getargnum 15 1 60 "${_prefix}.stop_timeout=" -d -y "SALT_STOP_TIMEOUT=")
export SALT_STOP_TIMEOUT

salt_device=$(getarg "${_prefix}.device=" -d -y "salt_device")
export salt_device

# Terminal naming modifiers
getargbool 0 "${_prefix}.nosuffix" -d -y "DISABLE_UNIQUE_SUFFIX=" && DISABLE_UNIQUE_SUFFIX=1
export DISABLE_UNIQUE_SUFFIX
getargbool 0 "${_prefix}.nohostname" -d -y "DISABLE_HOSTNAME_ID=" && DISABLE_HOSTNAME_ID=1
export DISABLE_HOSTNAME_ID
getargbool 0 "${_prefix}.noprefix" -d -y "DISABLE_ID_PREFIX=" && DISABLE_ID_PREFIX=1
export DISABLE_ID_PREFIX
getargbool 0 "${_prefix}.usefqdn" -d -y "USE_FQDN_MINION_ID=" && USE_FQDN_MINION_ID=1
export USE_FQDN_MINION_ID
getargbool 0 "${_prefix}.usemac" -d -y "USE_MAC_MINION_ID=" && USE_MAC_MINION_ID=1
export USE_MAC_MINION_ID

# Debugging
getargbool 0 "${_prefix}.debug=" -d -y "kiwidebug=" && kiwidebug=1
export kiwidebug
