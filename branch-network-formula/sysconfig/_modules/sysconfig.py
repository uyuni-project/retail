# -*- coding: utf-8 -*-
'''
Read and write sysconfig files to and from dictionay

:maintainer: <oholecek@suse.com>
:maturity: new
:depends: re
:platform: all

'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import re
import os

# Import Salt libs
import salt.utils.files
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError

__virtualname__ = 'sysconfig'


def __virtual__():
    '''
    Only run on Linux systems
    '''
    return __grains__['kernel'] == 'Linux' and __virtualname__ or False

def _get_content(filename):
    content = ''
    try:
        with salt.utils.files.fopen(filename) as rfh:
            content = salt.utils.stringutils.to_unicode(rfh.read())
    except (OSError, IOError) as exc:
        raise CommandExecutionError(
            "Unable to open file '{0}'. "
            "Exception: {1}".format(filename, exc)
        )
    return content

def read(filename, separator='=', field_separator=' '):
    '''
    Get sysconfig file as a dictionary with values as a list
    '''
    data = {}
    content = _get_content(filename)

    sysconfig_regx = re.compile(r'^\s*(?P<key>\w+)\s*' + separator + '\s*(?P<quote>[\'"])?(?P<value>.*?)(?P=quote)?\s*$', flags=re.M)
    values_regx = re.compile(r'(["\'].*?["\'])|' + field_separator)

    # need to parse values for either None in case of i.e. 'KEY=' and double quotes ie. 'KEY="VA LUE"'. Need to translate " to '.
    for m in sysconfig_regx.finditer(content):
        key = m.group('key')
        values = list()
        for v in values_regx.split(m.group('value')):
            if not v:
                values.append('')
                continue
            values.append(re.sub(r'"', "'", v))
        data[key] = values

    return data

def write(filename, data={}, separator='=', field_separator=' ', strict=False):
    '''
    Update sysconfig file by provided data. If strict is true, replace sysconfig with provided data
    '''
    if __opts__['test']:
        return None
    content = ''
    if strict:
        for key, values in data.items():
            if values is list:
                values = field_separator.join(values)
            content += '{}{}"{}"{}'.format(key, separator, values, "\n")
    else:
        content = _get_content(filename)
        for key, values in data.items():
            if type(values) is list:
                if len(values) == 1:
                    values = values[0]
                else:
                    values = field_separator.join(values)
            line = '{}{}"{}"'.format(key, separator, values)
            content, changes = re.subn(r'^\s*' + key + '\s*' + separator + '.*$', line, content, count=1, flags=re.M)
            if changes == 0:
                # pattern not found in file, append the option
                content += "{}\n".format(line)
                print("not found {}. Adding {}".format(key, line))

    bname = os.path.basename(filename)
    dname = os.path.dirname(os.path.abspath(filename))
    tempfile = salt.utils.files.mkstemp(prefix=bname, dir=dname)
    try:
        with salt.utils.files.fopen(tempfile, 'w') as wfh:
            wfh.write(content)
        salt.utils.files.rename(tempfile, filename)
    except (OSError, IOError) as exc:
        salt.utils.files.rm_rf(tempfile)
        raise CommandExecutionError(
            "Unable to write file '{0}'. "
            "Exception: {1}".format(filename, exc)
        )
