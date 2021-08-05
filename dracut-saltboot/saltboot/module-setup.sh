#!/bin/bash

# called by dracut
check() {
    return 0
}

# called by dracut
depends() {
    echo network dm
    return 0
}

get_python_pkg_deps() {
    rpm -q --requires "$@" |grep ^python3 | while read req ver; do
        rpm -q --whatprovides "$req"
    done | sort -u
}

get_python_pkg_deps_recursive() {
    deps="$@"
    res=$deps
    while [ -n "$deps" ] ; do
       deps=$(get_python_pkg_deps $deps)
       res=$(echo -e "$res\n$deps" |sort -u)
    done
    echo $res
}

# fix for bsc#1188846 - solve dependencies of nonexecutable python libs
fix_python_deps() {
    while read file ; do
        echo "$file"
        if [[ $file = *.so && ! -x $file ]] ; then
            for lib in $(ldd "$file" 2>/dev/null ); do
                [[ $lib != /* ]] && continue
                [[ -f $lib ]] || continue
                echo $lib
            done
        fi
    done
}


# called by dracut
installkernel() {
    # for raid and crypt support, the kernel module is needed unconditionally, even in hostonly mode
    hostonly='' instmods raid1 dm_crypt =crypto
}


# called by dracut
install() {
    inst_multiple -o $(rpm -ql $(get_python_pkg_deps_recursive salt salt-minion) | \
                  grep -v '\.pyc$\|/etc/salt/minion_id\|/etc/salt/pki\|/usr/share/doc/\|/usr/share/man' | \
                  fix_python_deps )
    inst_multiple -o /usr/lib64/libffi.so.7 # dracut dependency solver does not see this
    inst_multiple -o grep dig ldconfig date dbus-uuidgen systemd-machine-id-setup dmidecode seq parted \
                     lsblk partprobe mdadm dcounter mkswap curl head md5sum resize2fs mkfs mkfs.btrfs \
                     mkfs.ext2 mkfs.ext3 mkfs.ext4 mkfs.fat mkfs.vfat mkfs.xfs sync cryptsetup busybox \
                     swapon tail wipefs

    inst_hook cmdline 91 "$moddir/saltboot-root.sh"
    inst_hook pre-mount 99 "$moddir/saltboot.sh"
    inst_hook initqueue/timeout 99 "$moddir/saltboot-timeout.sh"

    echo "rd.neednet=1 rd.auto" > "${initdir}/etc/cmdline.d/50saltboot.conf"

    # wicked duid generation rules - use ll instead of default llt. ll does not include time, just mac address and generic prefix
    mkdir -p "${initdir}/etc/wicked"
    echo "<config><addrconf><dhcp6><default-duid><ll/></default-duid></dhcp6></addrconf></config>" > "${initdir}/etc/wicked/client.xml"

    inst -o /etc/salt/minion.d/autosign-grains.conf
}

