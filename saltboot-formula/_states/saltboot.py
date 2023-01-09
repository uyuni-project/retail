import salt.exceptions
import random
import string
import logging
import time
import os
import json
try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse
from distutils.version import LooseVersion
log = logging.getLogger(__name__)

# return device file for partition n on disk disk_device
def _part_device(disk_device, n):

    if (disk_device.startswith("/dev/disk/") or
        disk_device.startswith("/dev/mapper/") ):
        return "{0}-part{1}".format(disk_device, n)

    if disk_device[-1].isdigit():
        return "{0}p{1}".format(disk_device, n)

    return "{0}{1}".format(disk_device, n)


def _lsblk_compat(device):
    res = __salt__['cmd.run_all']("lsblk -J -p {0}".format(device), output_loglevel='trace')
    if res['retcode'] == 0:
        return json.loads(res['stdout'])

    res = __salt__['cmd.run_all']("lsblk -n -r -o MOUNTPOINT,FSTYPE,NAME {0}".format(device), output_loglevel='trace')

    ret = None
    for i, line in enumerate(res['stdout'].splitlines()):
        mountpoint, fstype, name = line.split(' ')[0:3]
        if i == 0:
            ret = {
                'blockdevices': [
                    { 'name': '/dev/' + name, 'type': fstype or None, 'mountpoint': mountpoint or None, 'children' : [] }
                ]
            }
        else:
            ret['blockdevices'][0]['children'].append({ 'name': '/dev/' + name, 'type': fstype or None, 'mountpoint': mountpoint or None})
    return ret

def _findmnt_compat(device):
    res = __salt__['cmd.run_all']("findmnt -J --submounts {0}".format(device), output_loglevel='trace')
    if res['retcode'] == 0:
        return json.loads(res['stdout'])

    res = __salt__['cmd.run_all']("findmnt -r -n -o TARGET,SOURCE --submounts {0}".format(device), output_loglevel='trace')

    ret = None
    for i, line in enumerate(res['stdout'].splitlines()):
        target, source = line.split(' ')[0:3]
        if i == 0:
            ret = {
                'filesystems': [
                    { 'target': target or None, 'source': source or None, 'children' : [] }
                ]
            }
        else:
            ret['filesystems'][0]['children'].append({'target': target or None, 'source': source or None})
    return ret

# try to recursively umount partition, failure is allowed, no error reporting
def _try_umount_device(device, depth = 0):
    tree = _lsblk_compat(device)
    if not tree:
        return
    devtree = tree['blockdevices'][0] # there should be exactly one device in the lsblk output

    log.debug("_try_umount_device {0} {1} {2}".format(device, depth, devtree))

    for c in devtree.get('children', []):
        _try_umount_device(c['name'], depth + 1)

    if devtree.get('mountpoint') == '[SWAP]':
        __salt__['cmd.run_all']("swapoff " + device, output_loglevel='trace')
    elif devtree.get('mountpoint'):
        # check submounts first
        mnt_tree = _findmnt_compat(device)
        if mnt_tree:
            for c in mnt_tree['filesystems'][0].get('children', []):
                _try_umount_device(c['source'], depth + 1)

        __salt__['cmd.run_all']("umount " + device, output_loglevel='trace')

    if devtree.get('type') == 'crypt':
        __salt__['cmd.run_all']("cryptsetup close " + device, output_loglevel='trace')
    elif depth > 0 and devtree.get('type', '').startswith('raid'):
        __salt__['cmd.run_all']("mdadm --stop " + device, output_loglevel='trace')
        for i in range(5):
            # verify that the raid is already stopped - it may take some time
            tree = _lsblk_compat(device)
            if tree:
                devtree = tree['blockdevices'][0]
                if devtree.get('type', '').startswith('raid'):
                    __salt__['cmd.run_all']("mdadm --stop " + device, output_loglevel='trace')
                    time.sleep(1)
                    continue
            break
    else:
        # there can be inactive raids (not listed by lsblk) that blocks the device anyway
        uuid = _mdadm_examine(device).get('MD_UUID')
        if uuid is not None:
            for raid_dev in __salt__['raid.list']().keys():
                raid_detail = __salt__['raid.detail'](raid_dev)
                if raid_detail.get('uuid') == uuid:
                    if os.path.exists(raid_dev):
                        _try_umount_device(raid_dev, depth + 1)
                    # inactive raids are invisible to lsblk and other tools
                    # call mdadm --stop unconditionally to be sure
                    __salt__['cmd.run_all']("mdadm --stop " + raid_dev, output_loglevel='trace')

# wipe all raid signatures on disk
# the partitions are supposed to be unmounted
def _disk_wipe_signatures(device):
    tree = _lsblk_compat(device)
    if not tree:
        return

    devtree = tree['blockdevices'][0] # there should be exactly one device in the lsblk output

    log.debug("_disk_wipe_signatures {0} {1}".format(device, devtree))

    for c in devtree.get('children', []):
       __salt__['cmd.run_all']("mdadm --zero-superblock {0}".format(c['name']), output_loglevel='trace')
    __salt__['cmd.run_all']("mdadm --zero-superblock {0}".format(device), output_loglevel='trace')


def _random_string(n):
    return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(n))

def _luks_name(device):
    return 'luks_' + device.split('/')[-1]

def _luks_open(device, luks_pass = None):
    if luks_pass is not None:
        luks_name = _luks_name(device)
        luks_device = "/dev/mapper/" + luks_name
        res = __salt__['file.is_blkdev'](luks_device)
        if res:
            log.debug("_luks_open: already opened: " + luks_device)

            return luks_device
        res = __salt__['cmd.run_all']("echo {0} | cryptsetup open --type luks {1} {2}".format(luks_pass, device, luks_name), python_shell=True)
        log.debug("_luks_open: {0} res: {1}".format(luks_device, res))
        if res['retcode'] != 0:
            return None
    else:
        luks_device = device
        log.debug("_luks_open: not encrypted: " + device)
    return luks_device

def _luks_create(device, luks_pass):
    res = __salt__['cmd.run_all']("echo {0} | cryptsetup --force-password luksFormat {1}".format(luks_pass, device), python_shell=True)
    log.debug("_luks_create: {0} res: {1}".format(device, res))
    if res['retcode'] != 0:
        return None
    return _luks_open(device, luks_pass)

def _mount(mountpoint, device, luks_pass = None):
    device = _luks_open(device, luks_pass)
    if not device:
        log.error('_mount: _luks_open failed')
        return False
    return __salt__['mount.mount'](mountpoint, device, True)


# if the device is already mounted, return mountpoint
# otherwise create a new mountpoint and mount it
# second return value indicates if the device was mounted by this function and needs umount
def _tmp_mount(device, mount = True, luks_pass = None):
    tree = _lsblk_compat(device)

    log.debug("_tmp_mount: {0}".format(tree))
    if tree:
        devtree = tree['blockdevices'][0] # there should be exactly one device in the lsblk output

        if luks_pass is None:
            if devtree.get('mountpoint') is not None:
                log.debug("_tmp_mount: already mounted on " + devtree.get('mountpoint'))
                return devtree.get('mountpoint'), False
        else:
            children = devtree.get('children', [])
            if len(children) == 1 and children[0].get('type') == 'crypt' and children[0].get('mountpoint') is not None:
                 log.debug("_tmp_mount: luks already opened and mounted on " + children[0].get('mountpoint'))
                 return children[0].get('mountpoint'), False

    if not mount:
        return None, False

    mountpoint = os.path.join('/var/adm/mount/', _random_string(32))
    res = _mount(mountpoint, device, luks_pass)
    if res:
        log.debug('_tmp_mount: {0} mounted on {1}'.format(device, mountpoint))
        return mountpoint, True

    log.error('_tmp_mount: mount failed {0}'.format(res))

    return None, False


def _get_service_partition(devmap):
    for p in devmap.values():
        if p.get('mountpoint') == '/srv/saltboot':
            return p
    return None


# parse partition size returned by __salt__['partition.list']
def _parse_size_mib(str):
    if str.endswith('MiB'):
        str = str[:-3]
    return float(str)


# compute partitions start and end, based on the size
def _compute_start_end(part, disk_size):
    num_grow = 0
    size_known = 1
    for part_id in sorted(part):
        p = part[part_id]
        if 'size_MiB' in p:
            size_known += p['size_MiB']
        else:
            num_grow += 1

    if size_known > disk_size - 1:
        raise salt.exceptions.SaltException(
            'Sum of partition sizes ({0}MiB) exceeds disk size ({1}MiB)'.format(size_known, disk_size - 1))

    size_auto = 0
    if num_grow > 0:
        size_auto = int((disk_size - 1 - size_known) / num_grow)

    res = {}
    pos = 1
    for part_id in sorted(part):
        p = part[part_id]
        res_p = dict(p)
        if 'size_MiB' not in res_p:
            res_p['size_MiB'] = size_auto
        res_p['start'] = pos
        pos += res_p['size_MiB']
        res_p['end'] = pos
        res[part_id] = res_p
    return res


def _parse_part_flags(str_flags):
    ret = set()
    if not str_flags:
        return ret
    flags = [f.strip() for f in str_flags.split(',')]
    id_flags = {'type=82': 'swap', 'type=8e': 'lvm', 'type=fd': 'raid', 'type=ef': 'esp'}
    known_flags = ['lvm', 'swap', 'raid', 'esp', 'bios_grub', 'prep', 'msftdata', 'msftres', 'diag']
    for f in flags:
        if f in id_flags:
            ret.add(id_flags[f])
            continue
        if f not in known_flags:
            continue
        ret.add(f)
    return ret


def _compare_part_flags(existing, requested):
    existing = set(existing)
    requested = set(requested)

    to_add = requested.difference(existing)
    to_delete = existing.difference(requested)

    # swap flag on gpt is not supported in SLE12SP3 parted
    # missing swap flag in existing might just be incorrectly reported
    # -> pretend that everything is ok
    to_add.discard('swap')

    return len(to_add) == 0 and len(to_delete) == 0, to_add, to_delete


def _set_part_flags(device, disklabel, num, enable = [], disable = []):
    flags_str = ''
    for f in enable:
        if f == 'swap' and disklabel == 'msdos':
            flags_str += 'set {0} type 0x82 '.format(num, f)
            continue
        if f == 'swap' and disklabel == 'gpt':
            continue # not supported in SLE12SP3 parted
        flags_str += 'set {0} {1} on '.format(num, f)

    for f in disable:
        if f == 'swap' and disklabel == 'msdos':
            continue
        if f == 'swap' and disklabel == 'gpt':
            continue # not supported in SLE12SP3 parted
        flags_str += 'set {0} {1} off '.format(num, f)

    if len(flags_str) == 0:
        # no change, no need to run parted
        return {'retcode': 0}
    return __salt__['cmd.run_all'](
        'parted -m -s -- {0} {1}'.format(device, flags_str))


# compare computed partitions start and end with
# existing partitions
#
# Params:
# part - requested partitions processed by _compute_start_end
# existing - output from  __salt__['partition.list']
# diskdevice - disk device (/dev/sda)
#
# Return
# ok - true if no changes are needed
# part - list of requested partitions copied from input param, with added entries
# to_delete - partitions to delete
def _check_existing(part, existing, diskdevice, wait = 0):
    disk_size = _parse_size_mib(existing['info']['size'])
    ok = True
    for idx, part_id in enumerate(sorted(part)):
        p = part[part_id]
        p['exists'] = False
        for enum in existing['partitions'].keys():
            e = existing['partitions'][enum]
            existing_start = _parse_size_mib(e['start'])
            existing_end = _parse_size_mib(e['end'])
            # workaround for possible rounding problems at the end of disk
            # case from bsc#1136857:
            #  disk size: 10240MiB
            #  partition requested start: 513MiB   requested end: 10239MiB
            #
            #  partition created by parted:
            #  existing start: 513MiB   existing end: 10240MiB
            #
            #  this partition should match too
            #
            if p['start'] == existing_start and (p['end'] == existing_end or
               (p['end'] + 1 == existing_end and p['end'] + 1 == disk_size)):
                flags_ok, to_add, to_delete = _compare_part_flags(_parse_part_flags(e['flags']), _parse_part_flags(p.get('flags', '')))
                if not flags_ok:
                    continue # delete and create the partition again, to be sure
                device = _part_device(diskdevice, enum)
                for w in range(0, wait):
                    if os.path.exists(device):
                        break
                    time.sleep(1)
                if not os.path.exists(device):
                    continue
                p['exists'] = True
                p['device'] = device
                p['diskdevice'] = diskdevice
                e['keep'] = True
        ok = ok and p['exists']

    to_delete = []
    for d in sorted(existing['partitions']):
        if 'keep' not in existing['partitions'][d]:
            to_delete.append(d)

    ok = ok and len(to_delete) == 0

    return ok, part, to_delete

# merge changes returned by 2 state modules
def _add_change(changes, entry):
    for k in entry.keys():
        if k not in changes:
            changes[k] = []
        changes[k].append(entry[k])

# merge results of 2 state modules
def _append_ret(ret, ret1, alt_comment = None, alt_comment_no_change = None, alt_changes = None):
    new_changes = ret1['changes']
    new_comment = ret1['comment']
    if new_changes:
        if alt_changes is not None:
            new_changes = alt_changes
        if alt_comment is not None:
            new_comment = alt_comment

    if not new_changes and ret1['result']:
        if alt_comment_no_change is not None:
            new_comment = alt_comment_no_change

    _add_change(ret['changes'], new_changes)
    ret['comment'] += '\n' + new_comment

def _get_disk_device(name, data):
    device = data.get('device')

    if device is not None:
        if not __salt__['file.is_blkdev'](device):
            path, name = os.path.split(device)
            if path == '':
                path = '/dev/disk/by-path';
            found = __salt__['file.find'](path, name=name, type='b')
            if found:
                # the list is sorted so partitions come after the main device
                device = found[0]
    if device is None and data.get('type') == 'RAID':
       device = '/dev/{0}'.format(name)
    return device

def disk_partitioned(name, data):
    '''
    Ensure that the disk is partitioned

    name
        Disk name
    data
        pillar data


    Pillar data example:

        type: DISK
        device: /dev/sda
        disklabel: gpt
        partitions:
            p1:
                 size_MiB: 200
                 type: 83
                 format: ext4
                 mountpoint: /srv/saltboot
            p2:
                 size_MiB: 2000
                 type: 82
                 format: swap
            p3:
                 type: 83
                 mountpoint: /
                 image: JeOS
            p4:
                 size_MiB: 4000
                 type: 83
                 format: btrfs
                 mountpoint: /data


    '''
    ret = {
        'name': name,
        'changes': {},
        'result': True,
        'comment': '',
        'pchanges': {},
        }

    report_progress = False
    if not __opts__['test']:
        report_progress = __salt__['file.is_fifo']("/progress")

    device = _get_disk_device(name, data)

    if device is None:
        raise salt.exceptions.SaltInvocationError(
            "Device not specified for {0}".format(name))

    try:
        existing = __salt__['partition.list'](device, unit='MiB')
    except Exception as e:
        if "Problem encountered while parsing output from parted" in str(e):
            existing = {'info': {'partition table': 'unknown'}}
        else:
            raise e

    existing_disklabel = existing['info'].get('partition table')
    force_repartition = __grains__.get('saltboot_force_repartition', False)

    if existing_disklabel != data['disklabel'] or force_repartition:
        if __opts__['test']:
            ret['comment'] += 'Disk "{0}" will be formatted with label {1}.\n'.format(name, data['disklabel'])
            _add_change(ret['pchanges'], {
                'old': "disklabel: " + existing_disklabel,
                'new': "disklabel: " + data['disklabel'],
            })

            # Return ``None`` when running with ``test=true``.
            ret['result'] = None
            existing['partitions'] = {}
        else:
            if not __grains__.get('saltboot_initrd'):
                raise salt.exceptions.SaltInvocationError(
                    "'disk_partitioned' can be used only in initrd")

            if report_progress:
                __salt__['cmd.run_all']("echo 'Formatting {0} with label {1}' > /progress ".format(name, data['disklabel']), python_shell=True, output_loglevel='trace')

            _try_umount_device(device)
            _disk_wipe_signatures(device)

            res = __salt__['partition.mklabel'](device, data['disklabel'])
            ret['comment'] += 'Disk "{0}" has been formatted with label {1}.\n'.format(name, data['disklabel'])
            _add_change(ret['changes'], {
                'old': "disklabel: " + existing_disklabel,
                'new': "disklabel: " + data['disklabel'],
            })
            ret['comment'] += '\n'.join(res)
            # update existing ptable info
            existing = __salt__['partition.list'](device, unit='MiB')

    else:
        ret['comment'] += 'Disk "{0}" already has label {1}.\n'.format(name, data['disklabel'])

    disk_size = _parse_size_mib(existing['info']['size'])

    # call _compute_start_end early to check disk size
    part = _compute_start_end(data['partitions'], disk_size)

    ok, part, to_delete = _check_existing(part, existing, device)

    if not ok and not __opts__['test'] and not __grains__.get('saltboot_initrd'):
        raise salt.exceptions.SaltInvocationError(
            "'disk_partitioned' can be used only in initrd")

    for d in to_delete:
        if __opts__['test']:
            ret['comment'] += 'Partition {1} on disk "{0}" will be deleted.\n'.format(name, d)
            _add_change(ret['pchanges'], {
                'old': 'delete part' + d,
            })
            ret['result'] = None
        else:
            if report_progress:
                __salt__['cmd.run_all']("echo 'Deleting {1} on disk {0}' > /progress ".format(name, d), python_shell=True, output_loglevel='trace')

            _try_umount_device(_part_device(device, d))
            res = __salt__['partition.rm'](device, d)
            ret['comment'] += 'Partition {1} on disk "{0}" has been deleted.\n'.format(name, d)
            _add_change(ret['changes'], {
                'old': 'delete part' + d,
            })
            ret['comment'] += '\n'.join(res)

    for idx, part_id in enumerate(sorted(part)):
        p = part[part_id]

        # flags can exists in dict and be None, so check after get instead of using default value
        flags = p.get('flags')
        if not flags:
            flags = ''

        if p['exists']:
            ret['comment'] += 'Partition "{0}{1}" already exists.\n'.format(name, part_id)
        else:
            if __opts__['test']:
                ret['comment'] += 'Partition "{0}{1}" will be created.\n'.format(name, part_id)
                _add_change(ret['pchanges'], {
                    'new': "add " + name + part_id,
                })
                ret['result'] = None
            else:
                if report_progress:
                    __salt__['cmd.run_all']("echo 'Creating {0}{1}' > /progress ".format(name, part_id), python_shell=True, output_loglevel='trace')

                # parted sets partition type according to specified fstype and
                # for swap there is no other way to set it on SLE12SP3
                parted_fstype = 'ext2'
                if 'swap' in flags:
                    parted_fstype = 'linux-swap'

                # use cmd.run directly because partition.mkpart does not support --align
                # https://github.com/saltstack/salt/issues/24828
                res = __salt__['cmd.run_all'](
                    'parted -m -s --align optimal --wipesignatures -- {0} mkpart {1} {2} {3}MiB {4}MiB'.format(device, 'primary', parted_fstype, p['start'], p['end']))
                if res['retcode'] > 0 and "unrecognized option" in res['stderr']:
                    res = __salt__['cmd.run_all'](
                        'parted -m -s --align optimal -- {0} mkpart {1} {2} {3}MiB {4}MiB'.format(device, 'primary', parted_fstype, p['start'], p['end']))
                if res['retcode'] > 0:
                    ret['comment'] += 'Unable to create partition "{0}{1}".\n'.format(name, part_id) + res['stdout'] + res['stderr']
                    ret['result'] = False
                    return ret
                ret['comment'] += 'Partition "{0}{1}" has been created.\n'.format(name, part_id)

                res = _set_part_flags(device, data['disklabel'], idx + 1, enable=_parse_part_flags(flags))
                if res['retcode'] > 0:
                    ret['comment'] += 'Unable to set partition "{0}{1} flags {2}".\n'.format(name, part_id, flags) + res['stdout'] + res['stderr']
                    ret['result'] = False
                    return ret

                _add_change(ret['changes'], {
                    'new': "add " + name + part_id,
                })
    return ret

# return mapping disk_id + part_id -> partition data, including device, format, etc.
def _device_map(partitioning, types = None, only_existing = True):
    devmap = {}

    for disk_id in partitioning.keys():
        disk_data = partitioning[disk_id]

        if types is not None and disk_data.get('type', 'DISK') not in types:
            continue

        device = _get_disk_device(disk_id, disk_data)

        if disk_data.get('partitions'):
            for w in range(0, 10):
                if os.path.exists(device):
                    break
                time.sleep(1)
            if not os.path.exists(device):
                continue

            existing = __salt__['partition.list'](device, unit='MiB')
            disk_size = _parse_size_mib(existing['info']['size'])
            part = _compute_start_end(disk_data['partitions'], disk_size)
            ok, part, to_delete = _check_existing(part, existing, device, wait = 30)

            for idx, part_id in enumerate(sorted(part)):
                p = part[part_id]
                if p.get('device') or not only_existing:
                    devmap[disk_id + part_id] = p
        else:
            disk_data['device'] = device
            disk_data['diskdevice'] = device
            devmap[disk_id] = disk_data

    return devmap


#######################################################################################################################
# this is copied from salt/states/mdadm.py
# FIXME: it can be eventually upstreamed

# FIXME: this should go to salt module
def _mdadm_examine(dev):
    res = __salt__['cmd.run_all']('mdadm -Y -E {0}'.format(dev), output_loglevel='trace', python_shell=False)
    ret = {}

    for line in res['stdout'].splitlines():
        name, var = line.partition("=")[::2]
        ret[name] = var
    return ret

def _raid_present(name,
            level,
            devices,
            **kwargs):
    '''
    Verify that the raid is present

    .. versionchanged:: 2014.7.0

    name
        The name of raid device to be created

    level
                The RAID level to use when creating the raid.

    devices
        A list of devices used to build the array.

    kwargs
        Optional arguments to be passed to mdadm.

    Example:

    .. code-block:: yaml

        /dev/md0:
          raid.present:
            - level: 5
            - devices:
              - /dev/xvdd
              - /dev/xvde
              - /dev/xvdf
            - chunk: 256
            - run: True
    '''
    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}

    # Device exists
    # FIXME: add devices if it runs in degraded mode
    raids = __salt__['raid.list']()
    if raids.get(name):
        ret['comment'] = 'Raid {0} already present'.format(name)
        return ret

    # Decide whether to create or assemble
    missing = []
    uuid_dict = {}
    new_devices = []

    for dev in devices:
        if dev == 'missing' or not os.path.exists(dev):
            missing.append(dev)
            continue
        superblock = _mdadm_examine(dev)

        if 'MD_UUID' in superblock:
            uuid = superblock['MD_UUID']
            if uuid not in uuid_dict:
                uuid_dict[uuid] = []
            uuid_dict[uuid].append(dev)
        else:
            new_devices.append(dev)

    if len(uuid_dict) > 1:
        ret['comment'] = 'Devices are a mix of RAID constituents with multiple MD_UUIDs: {0}.'.format(uuid_dict.keys())
        ret['result'] = False
        return ret
    elif len(uuid_dict) == 1:
        with_superblock = list(uuid_dict.values())[0]
    else:
        with_superblock = []

    if len(with_superblock) > 0:
        do_assemble = True
        verb = 'assembled'
    else:
        if len(new_devices) == 0:
            ret['comment'] = 'All devices are missing: {0}.'.format(missing)
            ret['result'] = False
            return ret
        do_assemble = False
        verb = 'created'

    # If running with test use the test_mode with create or assemble
    if __opts__['test']:
        if do_assemble:
            res = __salt__['raid.assemble'](name,
                                            with_superblock,
                                            test_mode=True,
                                            **kwargs)
        else:
            res = __salt__['raid.create'](name,
                                          level,
                                          new_devices + ['missing'] * len(missing),
                                          test_mode=True,
                                          **kwargs)
        ret['comment'] = 'Raid will be {0} with: {1}'.format(verb, res)
        ret['result'] = None

        if do_assemble and len(new_devices) > 0:
            ret['comment'] += '\nNew devices will be added: {0}'.format(new_devices)

        if len(missing) > 0:
            ret['comment'] += '\nMissing devices: {0}'.format(missing)

        return ret

    # Attempt to create or assemble the array
    if do_assemble:
        __salt__['raid.assemble'](name,
                                  with_superblock,
                                  **kwargs)
    else:
        __salt__['raid.create'](name,
                                level,
                                new_devices + ['missing'] * len(missing),
                                **kwargs)

    raids = __salt__['raid.list']()
    changes = raids.get(name)
    if changes:
        ret['comment'] = 'Raid {0} {1}.'.format(name, verb)
        ret['changes'] = changes
        # Saving config
        __salt__['raid.save_config']()
    else:
        ret['comment'] = 'Raid {0} failed to be {1}.'.format(name, verb)
        ret['result'] = False

    if do_assemble and len(new_devices) > 0:
        for d in new_devices:
            # FIXME: this should go to salt module
            res = __salt__['cmd.run_all']('mdadm --manage {0} --add {1}'.format(name, d))
            if res['retcode'] > 0:
                ret['comment'] += 'Unable to add {0} to {1}.\n'.format(d, name) + res['stdout'] + res['stderr']
                ret['result'] = False
            else:
                ret['comment'] += 'Added new device {0} to {1}.\n'.format(d, name)

    if len(missing) > 0:
        ret['comment'] += '\nMissing devices: {0}'.format(missing)

    return ret

#######################################################################################################################


def raid_created(name, partitioning):
    devmap = _device_map(partitioning, ['DISK'])
    device = _get_disk_device(name, partitioning[name])

    report_progress = False
    if not __opts__['test']:
        report_progress = __salt__['file.is_fifo']("/progress")

    if report_progress:
        __salt__['cmd.run_all']("echo 'Preparing {0}' > /progress ".format(device), python_shell=True, output_loglevel='trace')

    components = []
    for d in partitioning[name].get('devices'):
        cdevice = devmap.get(d)
        if cdevice is None:
            # not found in mapping - use device directly
            cdevice = d
        else:
            if cdevice.get('partitions') or cdevice.get('image') or cdevice.get('format'):
                raise salt.exceptions.SaltException(
                    'RAID component {0} of {1} must not be formatted, partitoned nor have image assigned'.format(d, name))

            cdevice = cdevice['device']

        components.append(cdevice)
        _try_umount_device(cdevice)

    #return __states__['raid.present'](device, partitioning[name].get('level'), components, run=True)
    ret = _raid_present(device, partitioning[name].get('level'), components, run=True)

    if ret['result']:
        # If the device is already assembed, _raid_present does not run it. Make sure it is started now
        __salt__['cmd.run_all']("mdadm --assemble --run {0}".format(device), output_loglevel='trace')

    return ret

def device_formatted(name, partitioning):
    '''
    Ensure that the device is formatted as filesystem or swap

    name
        disk_id + part_id, points to pillar data, i. e. "disk1p1"
    partitioning
        pillar data


    Pillar data example:

    disk1:
        type: DISK
        device: /dev/sda
        disklabel: gpt
        partitions:
            p1:
                 size_MiB: 200
                 type: 83
                 format: ext4
                 mountpoint: /srv/saltboot
            p2:
                 size_MiB: 2000
                 type: 82
                 format: swap
            p3:
                 type: 83
                 mountpoint: /
                 image: JeOS
            p4:
                 size_MiB: 4000
                 type: 83
                 format: btrfs
                 mountpoint: /data


    '''
    ret = {
        'name': name,
        'changes': {},
        'result': True,
        'comment': '',
        'pchanges': {},
        }
    devmap = _device_map(partitioning)

    if name not in devmap:
        raise salt.exceptions.SaltInvocationError(
            "Device does not exist for {0}".format(name))

    device = devmap[name].get('device')
    if device is None:
        if __opts__['test']:
            ret['comment'] = "Device {0} does not exist (yet).".format(name)
            ret['result'] = None
        else:
            ret['comment'] = "Device {0} does not exist.".format(name)
            ret['result'] = False
        return ret

    report_progress = False
    if not __opts__['test']:
        report_progress = __salt__['file.is_fifo']("/progress")

    if report_progress:
        __salt__['cmd.run_all']("echo 'Preparing {0}' > /progress ".format(device), python_shell=True, output_loglevel='trace')

    if not __opts__['test']:
        _try_umount_device(device)

    # if the device was partitioned, wipe the partition table (can happen for raid devices)
    try:
        __salt__['cmd.run_all']("wipefs -a -f -t gpt,PMBR {0}".format(device), output_loglevel='trace')
    except:
        pass

    luks_pass = devmap[name].get('luks_pass')
    opened_device = _luks_open(device, luks_pass)
    if opened_device is None:
        if __opts__['test']:
            ret['comment'] = "Device {0} will be encrypted.".format(device)
            ret['result'] = None
            return ret
        else:
            opened_device = _luks_create(device, luks_pass)

    fs_type = devmap[name]['format']
    if fs_type == 'swap':
        ret = __states__['cmd.run']("mkswap -f {0}".format(opened_device))

        __salt__['cmd.run_all']("swapon {0}".format(opened_device))
        return ret
    return __states__['blockdev.formatted'](opened_device, fs_type, force=True)

# get image version and hash written to filesystem
def _get_image_version(device, luks_pass = None):
    namever = None
    h = None
    mountpoint, need_umount = _tmp_mount(device, luks_pass = luks_pass)
    log.debug("_get_image_version {0} {1} {2}".format(mountpoint, need_umount, device))
    if mountpoint is not None:
        if __salt__['file.file_exists'](os.path.join(mountpoint, 'etc/ImageVersion')):
            namever = str(__salt__['file.read'](os.path.join(mountpoint, 'etc/ImageVersion'))).rstrip()
        if (namever is not None and 
            __salt__['file.file_exists'](os.path.join(mountpoint, 'etc/ImageVersion-' + namever))):
            h = str(__salt__['file.read'](os.path.join(mountpoint, 'etc/ImageVersion-' + namever))).split()[0]

        if need_umount:
            _try_umount_device(device)
    log.debug("_get_image_version found {0} {1} ".format(namever, h))
    return namever, h

# write image version and hash to filesystem
def _write_image_version(device, namever, h, luks_pass = None):
    mountpoint, need_umount = _tmp_mount(device, luks_pass = luks_pass)
    log.debug("_write_image_version {0} {1}".format(mountpoint, need_umount))
    res = False
    if mountpoint:
        res = __salt__['file.write'](os.path.join(mountpoint, 'etc/ImageVersion'), namever)
        res = __salt__['file.write'](os.path.join(mountpoint, 'etc/ImageVersion-' + namever), h)

        if need_umount:
            _try_umount_device(device)

# get image configured for given partition pillar data
# handle multiple image versions
def _get_image_for_part(images, part):
    image_id = part.get('image')
    image_version = part.get('image_version')
    image_dict = None
    if image_version is not None:
        try:
            if image_version in images[image_id]:
                    image_dict = images[image_id][image_version]
            if image_dict is None:
                raise salt.exceptions.SaltException("requested image '{0}' version {1} not found in pillar".format(image_id, image_version))
        except KeyError:
            pass
    else:
        try:
            image_version_fallback = None
            sorted_versions = sorted(images[image_id].keys(), key=LooseVersion, reverse=True)
            for check_version in sorted_versions:
                if not images[image_id][check_version].get('inactive'):
                    if image_version_fallback is None:
                        image_version_fallback = check_version
                    if images[image_id][check_version].get('synced'):
                        image_version = check_version
                        break
            if image_version is None:
                # no synced version found, maybe we run against old SUMA server
                # try fallback to original behavior
                image_version = image_version_fallback
            image_dict = images[image_id][check_version]
        except KeyError:
            pass

    if image_dict is None:
        raise salt.exceptions.SaltException("requested image '{0}' not found in pillar".format(image_id))

    return image_id, image_version, image_dict

def _mangle_url(url):
    supported_protocols = [ 'http', 'https', 'ftp', 'tftp' ]

    url_p = urlparse(url)
    download_server = __salt__['pillar.get']('saltboot_download_server')
    download_scheme = __salt__['pillar.get']('saltboot_download_protocol')

    if (download_scheme and download_scheme != url_p.scheme):
        url_p = url_p._replace(scheme = download_scheme)

        if (url_p.scheme.startswith('http') and not url_p.path.startswith('/saltboot/')):
            url_p = url_p._replace(path='{0}{1}'.format('/saltboot', url_p.path))

        if (not url_p.scheme.startswith('http') and url_p.path.startswith('/saltboot/')):
            url_p = url_p._replace(path=url_p.path[9:])

    if (download_server):
        url_p = url_p._replace(netloc = download_server)

    if url_p.scheme not in supported_protocols:
        raise ValueError("Unknown scheme {0}.\n".format(url_p.scheme))

    return url_p

def _download_url_cmd(url, local_path):
    # {0} url, {1} scheme, {2} netloc, {3} path, {4} params, {5} query, {6} fragment
    # {7} username, {8} password, {9} hostname, {10} port,
    # {11} output file
    download_cmd = {
        'http' : 'curl -f -L {0} > {11}',
        'https': 'curl -k -f -L {0} > {11}',
        'ftp'  : 'curl -P - -f -L {0} > {11}',
        'tftp' : 'busybox tftp -b 65464 -g -l {11} -r {3} {9} ',
    }
    url_p = _mangle_url(url)
    cmd_template = download_cmd.get(url_p.scheme, 'curl -f -L {0} > {11}')

    return cmd_template.format(url_p.geturl(),
          url_p.scheme, url_p.netloc, url_p.path, url_p.params, url_p.query, url_p.fragment,
          url_p.username, url_p.password, url_p.hostname, url_p.port, local_path)

def _deploy_cmd(url):
    # {0} url, {1} scheme, {2} netloc, {3} path, {4} params, {5} query, {6} fragment
    # {7} username, {8} password, {9} hostname, {10} port,
    download_pipe = {
        'http' : 'set -o pipefail;curl -f -L {0} ',
        'https': 'set -o pipefail;curl -k -f -L {0} ',
        'ftp'  : 'set -o pipefail;curl -P - -f -L {0} ',
        'tftp' : 'set -o pipefail;busybox tftp -b 65464 -g -l /dev/stdout -r {3} {9} ',
    }

    url_p = _mangle_url(url)
    cmd_template = download_pipe.get(url_p.scheme, 'curl -f -L {0} ')

    return cmd_template.format(url_p.geturl(),
          url_p.scheme, url_p.netloc, url_p.path, url_p.params, url_p.query, url_p.fragment,
          url_p.username, url_p.password, url_p.hostname, url_p.port)

_uncompress_pipe = {
    '': '',
    'gz': '| gzip -d',
    'gzip': '| gzip -d',
    'bz': '| bzip -d',
    'bzip': '| bzip -d',
    'xz': '| xz -d'
}


def image_downloaded(name, partitioning, images, service_mountpoint=None, mode='fill_cache'):
    '''
    Download an image to the cache on service partition or to the target device (depending on mode)

    name
        disk_id + part_id, points to pillar data, i. e. "disk1p1"
    partitioning
        pillar data
    images
        pillar data
    mode
        one of
          'fill_cache' - download image to cache
          'use_cache' - download image to the target device, use cached image if possible
          'ignore_cache' - download image to the target device, ignore cached image

    service_mountpoint
        mountpoint of service partition, needs to be specified for 'use_cache' mode


    Partitioning pillar data example:

    disk1:
        type: DISK
        device: /dev/sda
        disklabel: gpt
        partitions:
            p1:
                 size_MiB: 200
                 type: 83
                 format: ext4
                 mountpoint: /srv/saltboot
            p2:
                 size_MiB: 2000
                 type: 82
                 format: swap
            p3:
                 type: 83
                 mountpoint: /
                 image: JeOS
            p4:
                 size_MiB: 4000
                 type: 83
                 format: btrfs
                 mountpoint: /data

    Images pillar data example:

    JeOS:
        - 5.0.0:
            url: http://branchserver/pub/POS_Image_JeOS5.x86_64-5.0.0.gz
            name: POS_Image_JeOS5
            compressed: gzip
            fstype: ext3
            size: 1121976320
            hash: b8fef0e2d1f1cc4df41b957c8def0ff0
    '''

    def _get_cmd_for_hash(h):
        cmd_by_length = {
            32:  'md5sum',
            40:  'sha1sum',
            56:  'sha224sum',
            64:  'sha256sum',
            96:  'sha384sum',
            128: 'sha512sum'
        }
        l = len(h)
        try:
            return cmd_by_length[l]
        except:
            raise salt.exceptions.SaltException("unsupported hash '{0}', len {1}".format(h, l))

    ret = {
        'name': name,
        'changes': {},
        'result': True,
        'comment': '',
        'pchanges': {},
        }

    devmap = _device_map(partitioning, only_existing=False)

    if name not in devmap:
        raise salt.exceptions.SaltInvocationError(
            "Device does not exist for {0}".format(name))

    if mode != 'fill_cache': # we actually don't need the device for filling cache
        device = devmap[name].get('device')
        if device is None:
            if __opts__['test']:
                ret['comment'] = "Device {0} does not exist (yet).".format(name)
                ret['result'] = None
            else:
                ret['comment'] = "Device {0} does not exist.".format(name)
                ret['result'] = False
            return ret

    report_progress = False
    if not __opts__['test']:
        report_progress = __salt__['file.is_fifo']("/progress")
    dcounter_progress_file = "/progress"
    if __salt__['file.file_exists']("/dc_progress"):
        dcounter_progress_file = "/dc_progress"

    image_id, image_version, image = _get_image_for_part(images, devmap[name])

    compr = image.get('compressed', '')
    if compr not in _uncompress_pipe:
        ret['comment'] += "Unknown compression {0}.\n".format(compr)
        ret['result'] = False

    try:
        deploy_cmd = _deploy_cmd(image['url'])
    except ValueError as e:
        ret['comment'] += str(e.args)
        ret['result']   = False

    if not ret['result']:
        return ret

    if mode == 'fill_cache':
        need_umount = False
        if service_mountpoint is None:
            service_partition = _get_service_partition(devmap)
            if service_partition and not service_partition.get('device'):
                ret['comment'] = "Service partition device is not available, please check the partitioning pillar"
                ret['result'] = False
                return ret

            if service_partition:
                service_mountpoint, need_umount = _tmp_mount(service_partition['device'], True, service_partition.get('luks_pass'))

        if service_mountpoint is None:
            ret['comment'] = "Service partition is needed"
            ret['result'] = False
            return ret

        cache_path = service_mountpoint + urlparse(image['url']).path

        if __salt__['file.file_exists'](cache_path) and str(__salt__['file.read'](cache_path + '.hash')).rstrip() == image.get('hash'):
            ret['comment'] += "Found cached image {0}.\n".format(cache_path)

            if compr:
                h = image['compressed_hash']
            else:
                h = image['hash']
            res = __salt__['cmd.run_stdout']('{0} {1}'.format(_get_cmd_for_hash(h), cache_path), python_shell=True)
            if res.startswith(h):
                ret['comment'] += 'Checksum OK.'
                return ret

        ret['comment'] += 'Downloading image using {0} to cache {1}'.format(deploy_cmd, cache_path)
        res = __salt__['cmd.run_all']('mkdir -p {0}; {1} > {2}'.format(os.path.dirname(cache_path), deploy_cmd, cache_path), python_shell=True)

        if need_umount:
            _try_umount_device(service_partition['device'])

        if res['retcode'] > 0:
           ret['comment'] += 'Unable to download image {0}-{1}.\n'.format(image['name'], image_version) + res['stdout'] + res['stderr']
           ret['result'] = False
           return ret

        ret['comment'] += 'Image {0}-{1} successfully downloaded.\n'.format(image['name'], image_version)
        _add_change(ret['changes'], {
           'new': '{0}-{1}'.format(image['name'], image_version),
        })

        __salt__['file.write'](cache_path + '.hash', image.get('hash'))

        return ret

    deploy_comment = 'Downloading image using {0}'.format(deploy_cmd)
    if service_mountpoint and mode == 'use_cache':
        cache_path = service_mountpoint + urlparse(image['url']).path
        img_exists = __salt__['file.file_exists'](cache_path)
        hash_exists = __salt__['file.file_exists'](cache_path + '.hash')
        log.debug('check cache path {0}: exists {1}, hash {2}'.format(cache_path, img_exists, hash_exists))
        if img_exists and hash_exists:
            cache_hash = str(__salt__['file.read'](cache_path + '.hash')).rstrip()
            pillar_hash = image.get('hash')
            log.debug('cache hash "{0}", pillar hash "{1}"'.format(cache_hash, pillar_hash))
            if cache_hash == pillar_hash:
                log.debug('Using cached copy of image {0}-{1}.'.format(image['name'], image_version))
                # override deploy_cmd if we have a cached copy
                deploy_comment = 'Using cached copy of image {0}-{1}.'.format(image['name'], image_version)
                deploy_cmd = 'set -o pipefail; cat {0} '.format(cache_path)


    ret['comment'] += deploy_comment
    deploy_cmd += _uncompress_pipe[compr]

    _try_umount_device(device)

    if report_progress:
        deploy_cmd += " | dcounter -s {0} -l 'Downloading {1}-{2}' 2>>{3} ".format(int( image['size'] / (1024*1024) ), image['name'], image_version, dcounter_progress_file)

    res = __salt__['cmd.run_all']('{0} > {1}'.format(deploy_cmd, device), python_shell=True)

    if res['retcode'] > 0:
        ret['comment'] += 'Unable to deploy image {0}-{1} on {2}.\n'.format(image['name'], image_version, name) + res['stdout'] + res['stderr']
        ret['result'] = False
        return ret
    _add_change(ret['changes'], {
        'new': '{0}-{1}'.format(image['name'], image_version),
    })

    if 'hash' in image and 'size' in image:
        verify_cmd = 'head --bytes={1} {0}'.format(device, image['size'])
        if report_progress:
            verify_cmd += " | dcounter -s {0} -l 'Verifying {1}-{2}' 2>>{3} ".format(int( image['size'] / (1024*1024) ), image['name'], image_version, dcounter_progress_file)

        verify_cmd += ' | ' + _get_cmd_for_hash(image['hash']) + ' -'

        res = __salt__['cmd.run_all'](verify_cmd, python_shell=True)
        if res['retcode'] > 0:
            ret['comment'] += 'Unable to verify image {0}-{1} on {2}.\n'.format(image['name'], image_version, name) + res['stdout'] + res['stderr']
            ret['result'] = False
            if report_progress:
                __salt__['cmd.run_all']("echo 'Unable to verify image {0}-{1} on {2}' >/progress ".format(image['name'], image_version, name), python_shell=True)
            return ret
        h = res['stdout'][0:len(image['hash'])]
        if h != image['hash']:
            ret['comment'] += 'hash does not match on image {0}-{1} on {2}.\n'.format(image['name'], image_version, name) + res['stdout'] + res['stderr']
            ret['result'] = False
            if report_progress:
                __salt__['cmd.run_all']("echo 'hash does not match on image {0}-{1} on {2}' >/progress ".format(image['name'], image_version, name), python_shell=True)
            return ret
        ret['comment'] += 'hash OK\n'
    return ret

def image_deployed(name, partitioning, images):
    '''
    Ensure that the correct image is deployed on the partition

    name
        disk_id + part_id, points to pillar data, i. e. "disk1p1"
    partitioning
        pillar data
    images
        pillar data


    Partitioning pillar data example:

    disk1:
        type: DISK
        device: /dev/sda
        disklabel: gpt
        partitions:
            p1:
                 size_MiB: 200
                 type: 83
                 format: ext4
                 mountpoint: /srv/saltboot
            p2:
                 size_MiB: 2000
                 type: 82
                 format: swap
            p3:
                 type: 83
                 mountpoint: /
                 image: JeOS
            p4:
                 size_MiB: 4000
                 type: 83
                 format: btrfs
                 mountpoint: /data

    Images pillar data example:

    JeOS:
        - 5.0.0:
            url: http://branchserver/pub/POS_Image_JeOS5.x86_64-5.0.0.gz
            name: POS_Image_JeOS5
            compressed: gzip
            fstype: ext3
            size: 1121976320
            hash: b8fef0e2d1f1cc4df41b957c8def0ff0
    '''
    ret = {
        'name': name,
        'changes': {},
        'result': True,
        'comment': '',
        'pchanges': {},
        }


    devmap = _device_map(partitioning)
    if name not in devmap:
        raise salt.exceptions.SaltInvocationError(
            "Device does not exist for {0}".format(name))

    device = devmap[name].get('device')
    if device is None:
        if __opts__['test']:
            ret['comment'] = "Device {0} does not exist (yet).".format(name)
            ret['result'] = None
        else:
            ret['comment'] = "Device {0} does not exist.".format(name)
            ret['result'] = False
        return ret

    report_progress = False
    if not __opts__['test']:
        report_progress = __salt__['file.is_fifo']("/progress")

    image_id, image_version, image = _get_image_for_part(images, devmap[name])

    luks_pass = image.get('luks_pass')

    existing, existing_hash = _get_image_version(device, luks_pass)
    force_redeploy = __grains__.get('saltboot_force_redeploy', False)

    if ( existing is None or
         existing != '{0}-{1}'.format(image['name'], image_version) or
         ('hash' in image and existing_hash != image['hash'] ) or
         force_redeploy
       ):
        log.debug('existing: "{0}" existing hash: "{1}"'.format(existing, existing_hash))
        log.debug('new: "{0}-{1}" new hash: "{2}"'.format(image['name'], image_version, image.get('hash')))

        compr = image.get('compressed', '')
        if compr not in _uncompress_pipe:
            ret['comment'] += "Unknown compression {0}.\n".format(compr)
            ret['result'] = False

        if not ret['result']:
            return ret

        if __opts__['test']:
            ret['comment'] += 'Image {0}-{1} will be deployed on {2}.\n'.format(image['name'], image_version, name)
            _add_change(ret['pchanges'], {
                'new': '{0}-{1}'.format(image['name'], image_version),
                'old': existing
            })
            ret['result'] = None
        else:
            cache_failed = False
            service_partition = _get_service_partition(devmap)
            if service_partition:
                service_mountpoint, need_umount = _tmp_mount(service_partition['device'], True, service_partition.get('luks_pass'))
                log.debug('service partition mounted on {0}'.format(service_mountpoint))

                res = image_downloaded(name, partitioning, images, service_mountpoint, mode='use_cache')
                ret['comment'] += '\n' + res['comment']
                if res['result']:
                    _add_change(ret['changes'], res['changes'])
                else:
                    cache_failed = True

                if need_umount:
                    _try_umount_device(service_partition['device'])
            else:
                cache_failed = True # no service partition

            if cache_failed:
                res = image_downloaded(name, partitioning, images, mode='ignore_cache')
                ret['comment'] += res['comment']
                if res['result']:
                    _add_change(ret['changes'], res['changes'])
                else:
                    if existing:
                        checkdevice = _luks_open(device, luks_pass)
                        res = __salt__['cmd.run_all'](
                            'e2fsck -y -f {0}'.format(checkdevice))
                        if res['retcode'] == 0:
                            # re-read the existing version to make sure the original image is still OK
                            existing, existing_hash2 = _get_image_version(device, luks_pass)
                            if existing and existing_hash and existing_hash == existing_hash2:
                                ret['comment'] += "\nFallback to already installed image {0}\n".format(existing)
                                if report_progress:
                                    __salt__['cmd.run_all']("echo 'Fallback to already installed image {0}' > /progress ".format(existing), python_shell=True, output_loglevel='trace')

                                ret1 = __states__['file.managed'](
                                    '/salt_config',
                                    contents = [
                                    'export systemIntegrity=fine\n' +
                                    'export imageName={0}\n'.format(existing) +
                                    'export imageDiskDevice={0}\n'.format(devmap[name]['diskdevice'])
                                ])

                                __salt__['environ.setval']('saltboot_fallback', existing)
                                return ret

                    ret['result'] = False
                    return ret

            _add_change(ret['changes'], {'old': existing})

            if report_progress:
                __salt__['cmd.run_all']("echo 'Checking and resizing image filesystem' > /progress ", python_shell=True, output_loglevel='trace')

            checkdevice = _luks_open(device, luks_pass)
            res = __salt__['cmd.run_all'](
                'e2fsck -y -f {0} ; resize2fs {0}'.format(checkdevice), python_shell=True)
            if res['retcode'] > 0:
                ret['comment'] += 'Unable to resize image {0}-{1} on {2}.\n'.format(image['name'], image_version, name) + res['stdout'] + res['stderr']
                ret['result'] = False
                return ret

            if 'hash' in image:
                _write_image_version(device, '{0}-{1}'.format(image['name'], image_version), image['hash'], luks_pass)

            if devmap[name].get('mountpoint') == '/':
                ret1 = __states__['file.managed'](
                    '/salt_config',
                    contents = [
                        'export systemIntegrity=clean\n' +
                        'export imageName={0}-{1}\n'.format(image['name'], image_version) +
                        'export imageDiskDevice={0}\n'.format(devmap[name]['diskdevice'])
                    ])
                #_append_ret(ret, ret1) # the messages are confusing
    else:
        ret['comment'] += 'Image {0}-{1} is already deployed on {2}.\n'.format(image['name'], image_version, name)
        if not __opts__['test'] and devmap[name].get('mountpoint') == '/':
            ret1 = __states__['file.managed'](
                '/salt_config',
                contents = [
                    'export systemIntegrity=fine\n' +
                    'export imageName={0}-{1}\n'.format(image['name'], image_version) +
                    'export imageDiskDevice={0}\n'.format(devmap[name]['diskdevice'])
                ])
            #_append_ret(ret, ret1) # the messages are confusing

    return ret
 
def fstab_updated(name, partitioning, images):
    '''
    Ensure that the root partition is mounted on getenv(NEWROOT) and 
    $NEWROOT/etc/fstab is upddated according to partitioning
    and images pillar data.

    name
        not used
    partitioning
        pillar data
    images
        pillar data


    Partitioning pillar data example:

    disk1:
        type: DISK
        device: /dev/sda
        disklabel: gpt
        partitions:
            p1:
                 size_MiB: 200
                 type: 83
                 format: ext4
                 mountpoint: /srv/saltboot
            p2:
                 size_MiB: 2000
                 type: 82
                 format: swap
            p3:
                 type: 83
                 mountpoint: /
                 image: JeOS
            p4:
                 size_MiB: 4000
                 type: 83
                 format: btrfs
                 mountpoint: /data

    Images pillar data example:

    JeOS:
        - 5.0.0:
            url: http://branchserver/pub/POS_Image_JeOS5.x86_64-5.0.0.gz
            name: POS_Image_JeOS5
            compressed: gzip
            fstype: ext3
            size: 1121976320
            hash: b8fef0e2d1f1cc4df41b957c8def0ff0

    '''
    ret = {
        'name': name,
        'changes': {},
        'result': True,
        'comment': '',
        'pchanges': {},
        }

    newroot = __salt__['environ.get']("NEWROOT", default="/mnt")

    devmap = _device_map(partitioning)
    root_device = None


    report_progress = False
    if not __opts__['test']:
        report_progress = __salt__['file.is_fifo']("/progress")


    for p in devmap.values():
        if p.get('mountpoint') == '/':
            root_device = p
            if 'image' in p:
                image_id, image_version, image = _get_image_for_part(images, p)
                luks_pass = image.get('luks_pass')
            else:
                luks_pass = p.get('luks_pass')

        if 'device' not in p and 'mountpoint' in p:
            if __opts__['test']:
                ret['comment'] = "Device for mountpoint {0} does not exist (yet).".format(p.get('mountpoint'))
                ret['result'] = None
            else:
                ret['comment'] = "Device for mountpoint {0} does not exist.".format(p.get('mountpoint'))
                ret['result'] = False
            return ret



    if not __opts__['test']:
        if report_progress:
            __salt__['cmd.run_all']("echo 'Updating fstab' > /progress ", python_shell=True, output_loglevel='trace')

        if root_device is None:
            raise salt.exceptions.SaltInvocationError(
                "Device for / does not exist")


        _try_umount_device(root_device['device'])
        _mount(newroot, root_device['device'], luks_pass = luks_pass)


    prefix, need_umount = _tmp_mount(root_device['device'], mount = False, luks_pass = luks_pass)
    if prefix is None:
        if __opts__['test']:
            ret['comment'] = "Root partition is not mounted"
            ret['result'] = None
        else:
            ret['comment'] = "Root partition is not mounted"
            ret['result'] = False
        return ret

    ret1 = __states__['file.managed'](os.path.join(prefix, 'etc/fstab'), replace=True, contents = ["# Autogenerated with saltboot, DO NOT EDIT!"])
    _append_ret(ret, ret1, alt_comment = "fstab created", alt_comment_no_change = "fstab already exists", alt_changes = {'new': 'fstab created'})
    ret['result'] = ret['result'] and ret1['result']
    if not ret1['result']:
        return ret

    salt_device = root_device['device']
    boot_image = 'default'

    for p in devmap.values():
        if 'image' in p:
            image_id, image_version, image = _get_image_for_part(images, p)

            fstype = image.get('fstype')
            luks_pass = image.get('luks_pass')
            boot_image = image.get('boot_image', boot_image)
        else:
            fstype = p.get('format')
            luks_pass = p.get('luks_pass')

        if 'mountpoint' not in p and fstype != 'swap':
            continue

        name = p.get('mountpoint', 'swap')

        opened_device = _luks_open(p['device'], luks_pass)
        uuid = __salt__['disk.blkid'](opened_device)[opened_device]['UUID']

        if name != '/' and name != 'swap':
            __salt__['file.mkdir'](prefix + name)

        if name == '/etc/salt':
            salt_device = p['device']
            # we have to mount separate salt partition now, to be able
            # to copy salt configuration there
            _mount(prefix + '/etc/salt', p['device'], luks_pass = luks_pass)

        if name == '/boot/efi':
            _mount(prefix + '/boot/efi', p['device'], luks_pass = luks_pass)

        out = __salt__['mount.set_fstab'](name = name,
                                          device = "UUID=" + uuid,
                                          fstype = fstype,
                                          config = os.path.join(prefix, 'etc/fstab'),
                                          test = __opts__['test'],
                                          match_on = 'name')
        if out == 'present':
            ret['comment'] += "\n{0} already present in fstab".format(name)

        if __opts__['test']:
            if out == 'new':
                ret['comment'] += "\n{0} would be added".format(name)
                ret['result'] = None
            if out == 'change':
                ret['comment'] += "\n{0} would be updated".format(name)
                ret['result'] = None
        else:
            if out == 'new':
                _add_change(ret['changes'], {'add': name})
                ret['comment'] += "\n{0} added".format(name)
            if out == 'change':
                _add_change(ret['changes'], {'update': name})
                ret['comment'] += "\n{0} updated".format(name)

        if out == 'bad config':
            ret['result'] = False
            ret['comment'] += '\nfstab was not found.'
            return ret

    return ret

def bootloader_updated(name, partitioning, images, boot_images, terminal_kernel_parameters=None):
    '''
    Ensure that both local bootloader and pxe server are updated
    with current partitioning and image pillar,
    The root partition is expected to be mounted on getenv(NEWROOT)

    name
        not used
    partitioning
        pillar data
    images
        pillar data
    terminal_kernel_parameters
        additional kernel parameters

    Partitioning pillar data example:

    disk1:
        type: DISK
        device: /dev/sda
        disklabel: gpt
        partitions:
            p1:
                 size_MiB: 200
                 type: 83
                 format: ext4
                 mountpoint: /srv/saltboot
            p2:
                 size_MiB: 2000
                 type: 82
                 format: swap
            p3:
                 type: 83
                 mountpoint: /
                 image: JeOS
            p4:
                 size_MiB: 4000
                 type: 83
                 format: btrfs
                 mountpoint: /data

    Images pillar data example:

    JeOS:
        - 5.0.0:
            url: http://branchserver/pub/POS_Image_JeOS5.x86_64-5.0.0.gz
            name: POS_Image_JeOS5
            compressed: gzip
            fstype: ext3
            size: 1121976320
            hash: b8fef0e2d1f1cc4df41b957c8def0ff0

    '''

    ret = {
        'name': name,
        'changes': {},
        'result': True,
        'comment': '',
        'pchanges': {},
        }

    if __salt__['environ.get']('saltboot_fallback'):
        ret['comment'] = "Fallback to already installed {0}".format(__salt__['environ.get']('saltboot_fallback'))
        return ret

    devmap = _device_map(partitioning)
    root_device = None
    salt_device = None

    report_progress = False
    if not __opts__['test']:
        report_progress = __salt__['file.is_fifo']("/progress")

    if report_progress:
        __salt__['cmd.run_all']("echo 'Updating bootloader' > /progress ", python_shell=True, output_loglevel='trace')

    for p in devmap.values():
        if p.get('mountpoint') == '/':
            root_device = p
            if 'image' in p:
                image_id, image_version, image = _get_image_for_part(images, p)
                luks_pass = image.get('luks_pass')
            else:
                luks_pass = p.get('luks_pass')

        if p.get('mountpoint') == '/etc/salt':
            salt_device = p['device']

    prefix, need_umount = _tmp_mount(root_device['device'], mount = False, luks_pass = luks_pass)
    if prefix is None:
        if __opts__['test']:
            ret['comment'] = "Root partition is not mounted"
            ret['result'] = None
        else:
            ret['comment'] = "Root partition is not mounted"
            ret['result'] = False
        return ret

    boot_image_id = _get_boot_image(partitioning, images)
    boot_image = boot_images.get(boot_image_id)

    if salt_device is None:
        salt_device = root_device['device']

    ret['comment'] = "salt_device={0}\nboot_image={1}\nroot={2}\nterminal_kernel_parameters={3}".format(salt_device, boot_image_id, root_device['device'], terminal_kernel_parameters)

    if not __opts__['test']:
        if terminal_kernel_parameters is None:
            terminal_kernel_parameters = ''
        default_kernel_parameters = __salt__['environ.get']("DEFAULT_KERNEL_PARAMETERS", default="")

        # make sure raid is configured on local boot
        __salt__['cmd.run_all']("mdadm --detail --scan > {0}".format(os.path.join(prefix, 'etc/mdadm.conf')), python_shell=True, output_loglevel='trace')

        # notify branch server that the new config is in place
        __salt__['cmd.run_all']("salt-call event.send suse/manager/pxe_update 'salt_device={0}' 'boot_image={1}' 'root={2}' 'terminal_kernel_parameters={3}' with_grains=True".format(salt_device, boot_image_id, root_device['device'], terminal_kernel_parameters), python_shell=False, output_loglevel='trace')

        # this can be eventually used for kexec in verify_boot_image
        __salt__['cmd.run_all']("echo -n '{0} salt_device={1} root={2} {3}' >/update_kernel_cmdline".format(
            default_kernel_parameters, salt_device, root_device['device'], terminal_kernel_parameters), python_shell=True, output_loglevel='trace')

        # adjust grub configuration
        __salt__['file.replace'](os.path.join(prefix, 'etc/default/grub'), '^GRUB_CMDLINE_LINUX=.*', "GRUB_CMDLINE_LINUX='{0} {1}'".format(
            default_kernel_parameters, terminal_kernel_parameters), append_if_not_found=True)

        __salt__['cmd.run_all']('if [ -e /sys/firmware/efi ]; then sed -i -e "s|^LOADER_TYPE=.*|LOADER_TYPE=\\"grub2-efi\\"|" ' + prefix + '/etc/sysconfig/bootloader; else sed -i -e "s|^LOADER_TYPE=.*|LOADER_TYPE=\\"grub2\\"|" ' + prefix + '/etc/sysconfig/bootloader; fi', python_shell=True)

        if not os.path.exists(os.path.join(prefix, 'boot/grub2/grub.cfg')):
            # local boot is not configured
            # download kernel and initrd for kexec and for local boot
            #
            # failures do matter only if kernel version differs and kexec fails, so do not set ret['result'] here
            try:
                cmd = _download_url_cmd(boot_image.get('kernel', {}).get('url', ''), os.path.join(prefix, 'boot/Image'))
                res = __salt__['cmd.run_all'](cmd, python_shell=True)
                if res['retcode'] > 0:
                    ret['comment'] += "\nKernel download failed:\n" + cmd + " : " + res['stdout'] + res['stderr']
                cmd = _download_url_cmd(boot_image.get('initrd', {}).get('url', ''), os.path.join(prefix, 'boot/initrd'))
                res = __salt__['cmd.run_all'](cmd, python_shell=True)
                if res['retcode'] > 0:
                    ret['comment'] += "\nInitrd download failed:\n" + cmd + " : " + res['stdout'] + res['stderr']
            except ValueError as e:
                ret['comment'] += "\nCan't download current kernel/initrd: " + str(e.args)

            # install bootloader
            res = __salt__['cmd.run_chroot'](prefix, "sh -c 'mount -a ; pbl --install ; pbl --config ; test -f /boot/grub2/grub.cfg '", binds=["/dev", "/proc", "/sys"])
            if res['retcode'] > 0:
                ret['comment'] += '\nBootloader installation failed.\n' + res['stdout'] + res['stderr']

    return ret

# return boot image corresponding to system image mounted on /
def _get_boot_image(partitioning, images):

    boot_image_id = 'default'
    for disk_id in partitioning.keys():
        disk_data = partitioning[disk_id]
        if disk_data.get('disklabel') != 'none':
            part = disk_data.get('partitions')
            for part_id in sorted(part):
                p = part[part_id]
                if p.get('mountpoint') != '/' or p.get('image') is None:
                    continue
                image_id, image_version, image = _get_image_for_part(images, p)
                if image:
                    boot_image_id = image.get('boot_image', 'default')
                    break
        else:
            if disk_data.get('mountpoint') != '/' or disk_data.get('image') is None:
                continue
            image_id, image_version, image = _get_image_for_part(images, disk_data)
            if image:
                boot_image_id = image.get('boot_image', 'default')
                break

    return boot_image_id

def _check_terminal_kernel_parameters(parameters):
    if parameters is None:
        return True, 'OK'

    kernel_cmdline = str(__salt__['file.read']('/proc/cmdline')).split()

    ok = True
    msg = 'Missing kernel parameters: '

    for p in parameters.split():
        if p not in kernel_cmdline:
            ok = False
            msg = msg + ' ' + p
    if ok:
        msg = 'OK'
    return ok, msg

def _request_salt_stop():
    pid_file = '/var/run/salt-minion.pid'
    if __salt__['file.file_exists']('/usr/bin/venv-salt-minion'):
        pid_file = '/var/run/venv-salt-minion.pid'
    pid = __salt__['file.read'](pid_file)
    __salt__['file.write']('/root/saltstop', pid)
    return __states__['cmd.run']('sleep 3; kill {0}'.format(pid), bg=True)

def verify_and_boot_system(name, partitioning, images, boot_images, action = 'fail', terminal_kernel_parameters=None):

    ret = {
        'name': name,
        'changes': {},
        'result': True,
        'comment': '',
        'pchanges': {},
        }

    report_progress = False
    if not __opts__['test']:
        report_progress = __salt__['file.is_fifo']("/progress")

    newroot = __salt__['environ.get']("NEWROOT", default="/mnt")
    saltboot_fallback = __salt__['environ.get']('saltboot_fallback')

    if saltboot_fallback:
        ret['comment'] = "Fallback to already installed {0}".format(saltboot_fallback)
        if report_progress:
            __salt__['cmd.run_all']("echo 'Booting already installed {0}' > /progress ".format(saltboot_fallback), python_shell=True, output_loglevel='trace')
        res = _request_salt_stop()
        ret['comment'] += "\n" + res['comment']
        return ret

    boot_image_id = _get_boot_image(partitioning, images)
    boot_image = boot_images.get(boot_image_id)
    if boot_image is None:
        ret['comment'] += 'Boot image "{0}" not found in pillar.\n'.format(boot_image_id)
        ret['result'] = False
        return ret

    actual_kernel_version = __grains__.get('kernelrelease')
    requested_kernel_version = boot_image.get('kernel', {}).get('version', '')

    kernel_parameters_ok, kernel_parameters_msg = _check_terminal_kernel_parameters(terminal_kernel_parameters)

    if actual_kernel_version == requested_kernel_version and kernel_parameters_ok:
        ret['comment'] += 'Actual kernel version "{0}" matches the pillar for boot image "{1}, parameters are OK".\n'.format(requested_kernel_version, boot_image_id)

        if __opts__['test']:
            return ret

        if report_progress:
            ret['comment'] += 'Booting system'
            __salt__['cmd.run_all']("echo 'Booting system' > /progress ", python_shell=True, output_loglevel='trace')

        res = _request_salt_stop()
        ret['comment'] += "\n" + res['comment']
        return ret

    if actual_kernel_version != requested_kernel_version:
        ret['comment'] += 'Actual kernel version "{0}" does not match "{1}" from the pillar for boot image "{2}".\n'.format(actual_kernel_version, requested_kernel_version, boot_image_id)

    if not kernel_parameters_ok:
        ret['comment'] += '{0}\n'.format(kernel_parameters_msg)

    if report_progress:
        __salt__['cmd.run_all']("echo '{0}' > /progress ".format(ret['comment']), python_shell=True, output_loglevel='trace')

    if __opts__['test']:
        ret['result'] = None
        return ret

    if action == 'fail':
        ret['result'] = False
        return ret

    if action == 'kexec':
        kexec_opt = ''
        res = __salt__['cmd.run_all']("kexec --help |grep -q kexec-syscall-auto", python_shell=True)
        if res['retcode'] == 0:
            kexec_opt += "--kexec-syscall-auto "

        # try to load kexec
        cmd = 'kexec ' + kexec_opt + ' -l ' + newroot + '/boot/Image --reuse-cmdline --append="$(cat /update_kernel_cmdline)" --initrd=' + newroot + '/boot/initrd'

        res = __salt__['cmd.run_all'](cmd, python_shell=True)
        if res['retcode'] > 0:
            ret['comment'] += 'Kexec failed, doing normal reboot.\n' + res['stdout'] + res['stderr']
            action = 'reboot'

    __states__['file.append'](
        '/salt_config',
        text = 'export kernelAction={0}\n'.format(action)
        )

    res = _request_salt_stop()
    ret['comment'] += "\n" + res['comment']
    return ret
