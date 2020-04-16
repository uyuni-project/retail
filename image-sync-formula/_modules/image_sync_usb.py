import logging
log = logging.getLogger(__name__)


def create(dest, sizeMiB=300):

    srv_dir = __pillar__['branch_network']['srv_directory']

    # erase block device or create new file
    res = __salt__['cmd.run_all']("dd if=/dev/zero 'of={0}' bs=1M count={1}".format(dest, sizeMiB))
    if res['retcode'] > 0:
        return res

    dest_type = __salt__['file.stats'](dest)['type']

    res = __salt__['cmd.run_all']("parted '{0}' -- mklabel gpt".format(dest))
    if res['retcode'] > 0:
        return res

    res = __salt__['cmd.run_all']("parted '{0}' -- mkpart primary 1 3".format(dest))
    if res['retcode'] > 0:
        return res

    res = __salt__['cmd.run_all']("parted '{0}' -- name 1 grub".format(dest))
    if res['retcode'] > 0:
        return res

    res = __salt__['cmd.run_all']("parted '{0}' -- set 1 bios_grub on".format(dest))
    if res['retcode'] > 0:
        return res

    res = __salt__['cmd.run_all']("parted '{0}' -- mkpart primary 3 130".format(dest))
    if res['retcode'] > 0:
        return res

    res = __salt__['cmd.run_all']("parted '{0}' -- name 2 boot".format(dest))
    if res['retcode'] > 0:
        return res

    res = __salt__['cmd.run_all']("parted '{0}' -- set 2 boot on".format(dest))
    if res['retcode'] > 0:
        return res

    res = __salt__['cmd.run_all']("parted '{0}' -- mkpart primary 130 -1".format(dest))
    if res['retcode'] > 0:
        return res

    res = __salt__['cmd.run_all']("parted '{0}' -- name 3 main".format(dest))
    if res['retcode'] > 0:
        return res

    res = __salt__['cmd.run_all']("kpartx -av '{0}'".format(dest))
    if res['retcode'] > 0:
        return res

    devices = list(map(lambda l: "/dev/mapper/" + l.split()[2], res['stdout'].splitlines()))
    if dest_type == 'block':
        loopdev = dest
    else:
        loopdev = "/dev/" + res['stdout'].splitlines()[0].split()[2][:-2]

    res = __salt__['cmd.run_all']("mkdosfs '{0}'".format(devices[1]))
    if res['retcode'] > 0:
        return res

    res = __salt__['cmd.run_all']("mke2fs '{0}'".format(devices[2]))
    if res['retcode'] > 0:
        return res

    tmpmount = __salt__['temp.dir']()

    res = __salt__['cmd.run_all']("mount '{0}' '{1}'".format(devices[2], tmpmount))
    if res['retcode'] > 0:
        return res

    res = __salt__['cmd.run_all']("mkdir -p '{0}/boot/efi' '{0}/boot/pxelinux.cfg'".format(tmpmount))
    if res['retcode'] > 0:
        return res

    res = __salt__['cmd.run_all']("mount '{0}' '{1}/boot/efi'".format(devices[1], tmpmount))
    if res['retcode'] > 0:
        return res

    res = __salt__['cmd.run_all']("ln -s . grub2", cwd=tmpmount + "/boot")
    if res['retcode'] > 0:
        return res

    res = __salt__['cmd.run_all']("grub2-install --target=i386-pc --force --removable '--boot-directory={0}/boot' '{1}'".format(tmpmount, loopdev))
    if res['retcode'] > 0:
        return res

    res = __salt__['cmd.run_all']("grub2-install --target=x86_64-efi --force --removable --no-nvram '--boot-directory={0}/boot' '--efi-directory={0}/boot/efi' '{1}'".format(tmpmount, loopdev))
    if res['retcode'] > 0:
        return res

    res = __salt__['cmd.run_all']("cp -f '{0}/boot/grub.efi' '{1}/boot/efi/EFI/BOOT/GRUB.EFI'".format(srv_dir, tmpmount))
    if res['retcode'] > 0:
        return res

    res = __salt__['cmd.run_all']("cp -f '{0}/boot/shim.efi' '{1}/boot/efi/EFI/BOOT/BOOTX64.EFI'".format(srv_dir, tmpmount))
    if res['retcode'] > 0:
        return res

    uuid = __salt__['disk.blkid'](devices[2])[devices[2]]['UUID']

    configfile = ("search.fs_uuid " + uuid +" root\n"
                 +"set prefix=($root)/boot\n"
                 +"configfile ${prefix}/grub.cfg\n")

    __salt__['file.write']("{0}/boot/efi/EFI/BOOT/GRUB.CFG".format(tmpmount), configfile)

    res = __salt__['cmd.run_all']("cp '{0}/boot/linux' '{0}/boot/initrd.gz' '{0}/boot/grub.cfg' '{1}/boot'".format(srv_dir, tmpmount))
    if res['retcode'] > 0:
        return res

    res = __salt__['cmd.run_all']("cp '{0}/boot/pxelinux.cfg/default.grub2.cfg' '{1}/boot/pxelinux.cfg/'".format(srv_dir, tmpmount))
    if res['retcode'] > 0:
        return res

    res = __salt__['cmd.run_all']("umount '{0}/boot/efi'".format(tmpmount))
    if res['retcode'] > 0:
        return res

    res = __salt__['cmd.run_all']("umount '{0}'".format(tmpmount))
    if res['retcode'] > 0:
        return res

    res = __salt__['cmd.run_all']("kpartx -d '{0}'".format(dest))
    if res['retcode'] > 0:
        return res

    res = __salt__['cmd.run_all']("rmdir '{0}'".format(tmpmount))
    if res['retcode'] > 0:
        return res

    return {
        'retcode': 0,
        'stdout': '',
        'stderr': "USB image created"
    }
