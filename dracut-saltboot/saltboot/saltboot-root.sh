#!/bin/sh

if [ -z "$root" ] ; then
  root=saltboot
else
  # we have root, we can eventually continue without network after timeout
  # the timeout is controlled by rd.retry option
  echo "rm -f -- $hookdir/initqueue/finished/wait-network.sh" > $hookdir/initqueue/timeout/saltboot-network.sh
fi

rootok=1

# If we don't have a server, we need dhcp
if [ -z "$server" ] ; then
    DHCPORSERVER="1"
fi;

export MASTER=$(getarg MASTER=)
export MINION_ID_PREFIX=$(getarg MINION_ID_PREFIX=)
export DISABLE_UNIQUE_SUFFIX=$(getarg DISABLE_UNIQUE_SUFFIX=)
export SALT_TIMEOUT=$(getarg SALT_TIMEOUT=)
export salt_device=$(getarg salt_device=)
export kiwidebug=$(getarg kiwidebug=)
