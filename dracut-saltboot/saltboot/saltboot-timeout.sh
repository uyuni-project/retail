#!/bin/sh

type getarg >/dev/null 2>&1 || . /lib/dracut-lib.sh

# saltboot timeout script
# if $root is specified, usually means terminal is already deployed and thus network is optional
# wait for either network or device to boot from to be ready

if [ -z "$root" ] || [ "$root"x = "saltbootx" ]; then
  exit 0
fi

_name="$(str_replace "${root#block:}" '/' '\x2f')"
# shellcheck disable=SC2034
for f in wait-network.sh "devexists-$_name.sh"; do
  # shellcheck disable=SC2154
  if [ ! -e "$hookdir/initqueue/finished/\$f" ] || ( . "$hookdir/initqueue/finished/\$f" ); then
    rm -f -- "$hookdir/initqueue/finished/wait-network.sh"
    rm -f -- "$hookdir/initqueue/finished/devexists-$_name.sh"
  fi
done
