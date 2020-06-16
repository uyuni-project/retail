# -*- coding: utf-8 -*-
'''
Support for cryptsetup and handling encrypted volumes

Copyright 2019 SUSE LLC.

'''

import logging

import salt.utils.path

log = logging.getLogger(__name__)

def __virtual__():
    '''
    Check if cryptsetup is available and what version it is
    '''
    if salt.utils.path.which("cryptsetup"):
        return True

    return (
        False,
        "The cryptsetup execution module cannot be loaded: cryptsetup binary is not in the path.",
    )

def __is_luks2():
    return __cryptsetup_cmd("--version")["output"].split()[1].startswith('2.')

def __cryptsetup_cmd(cmd, luks_pass = None):
    '''
    Execute cryptsetup command and return result
    '''

    password_entry = ""
    if luks_pass:
        password_entry = "echo {0} |".format(luks_pass)
    cryptsetup_cmd = "{0}{1} {2}".format(password_entry, salt.utils.path.which("cryptsetup"), cmd)
    out = __salt__["cmd.run_all"](cryptsetup_cmd, python_shell=True)
    return out

def _luks_name(device):
    return 'luks_' + device.split('/')[-1]

def luks_open(device, luks_pass):
    '''
    Try to open encrypted device

    If encrypted device is already opened, do nothing.
    Returns None on failure
    '''

    if luks_pass is not None:
        luks_name = _luks_name(device)
        luks_device = "/dev/mapper/" + luks_name
        res = __salt__['file.is_blkdev'](luks_device)
        if res:
            log.debug("luks_open: already opened: " + luks_device)
            return luks_device

        luksOpen = "open --type luks"
        if not __is_luks2:
            luksOpen = "luksOpen"

        res = __cryptsetup_cmd("{0} {1} {2}".format(luksOpen, device, luks_name), luks_pass)
        log.debug("luks_open: {0} res: {1}".format(luks_device, res))
        if res["retcode"] != 0:
            return None
    else:
        luks_device = device
        log.debug("luks_open: not encrypted: " + device)
    return luks_device

def luks_create(device, luks_pass):
    '''
    Create encrypted device and open it

    Returns None on failure
    '''

    force_password = "--force-password"
    if not __is_luks2:
        force_password = ""

    res = __cryptsetup_cmd("{0} luksFormat {1}".format(force_password, device), luks_pass)
    log.debug("luks_create: {0} res: {1}".format(device, res))
    if res["retcode"] != 0:
        return None
    return luks_open(device, luks_pass)
