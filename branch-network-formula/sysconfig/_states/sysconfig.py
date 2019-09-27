# -*- coding: utf-8 -*-

'''
Manage sysconfig files
======================

:maintainer: <oholecek@suse.com>
:maturity: new
:depends: re
:platform: Linux
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
from salt.ext import six

__virtualname__ = 'sysconfig'

def __virtual__():
    '''
    Only load if the sysconfig module is available
    '''
    return __virtualname__ if 'sysconfig.read' in __salt__ else False

def _options_ops(op, name, options, separator, field_separator, strict):
    ret = {'name': name,
          'changes': {},
          'result': True,
          'comment': ''
          }
    config = {}
    try:
        config = __salt__['sysconfig.read'](name, separator=separator, field_separator=field_separator)
    except IOError as err:
        ret['comment'] = "{0}".format(err)
        ret['result'] = False
        return ret

    try:
        config_out = {}
        changes = {}
        if strict:
            for key_to_remove in set(config.keys()).difference(options.keys()):
                orig_value = config.pop(key_to_remove)
                changes[key_to_remove].update({key_to_remove: ''})
                changes[key_to_remove].update({key_to_remove: {'before': orig_value,
                                                               'after': None}})
        for option, values in options.items():
            cur_values = set(config.get(option, ''))
            new_values = set()
            # prevent iterable string to be decomposed into set of characters
            if type(values) == list:
                new_values = set(values)
            else:
                new_values.add(values)

            options_updated = set()
            if (op == 'present'):
                options_updated = new_values.union(cur_values)
            elif (op == 'absent'):
                options_updated = cur_values - new_values
            elif (op == 'set'):
                options_updated = new_values
            else:
                ret['comment'] = 'Unknown operation: {}'.format(op)
                ret['result'] = False
                return ret

            if cur_values != options_updated:
                if len(options_updated) == 1:
                    config_out[option] = next(iter(options_updated))
                else:
                    config_out[option] = list(options_updated)

                changes[option] = {'before' : cur_values,
                                   'after' : options_updated}
        if not __opts__['test']:
            __salt__['sysconfig.write'](name, config_out, separator=separator, field_separator=field_separator, strict=strict)
    except (IOError, KeyError) as err:
        ret['comment'] = "{0}".format(err)
        ret['result'] = False
        return ret
    if 'error' in changes:
        ret['result'] = False
        ret['comment'] = 'Errors encountered. {0}'.format(changes['error'])
        ret['changes'] = {}
    elif not changes:
        ret['comment'] = 'No changes detected'
    else:
        for name, body in changes.items():
            if body:
                if __opts__['test']:
                    ret['comment'] = 'Potentional changes'
                else:
                    ret['comment'] = 'Changes take effect'
                ret['changes'].update({name: changes[name]})
    return ret

def options_set(name, options={}, separator='=', field_separator=' ', strict=False):
    '''
    .. code-block:: yaml

      /home/saltminion/sysconfig:
        sysconfig.options_set:
          - separator: '='
          - options:
              test: 'testval'
              test:
                - 'val1'
                - 'val2'
              test2: 'testvalA testvalB'

    This makes sure specified values are the only present in given sysconfig
    file for specified keys.
    Values can be provided either as a list of strings or single string.

    Options in sysconfig file not specified in `options` dict
    will be untouched, unless `strict: True` flag is used.

    Changes dict will contain the list of changes made.
    '''
    return _options_ops('set', name, options, separator, field_separator, strict)


def options_present(name, options={}, separator='=', field_separator=' ', strict=False):
    '''
    .. code-block:: yaml

      /home/saltminion/sysconfig:
        sysconfig.options_present:
          - separator: '='
          - options:
              test: 'testval'
              test:
                - 'val1'
                - 'val2'
              test2: 'testvalA testvalB'

    This makes sure specified values are present in given sysconfig
    file for specified keys.
    Values can be provided either as a list of strings or single string.

    Unless `strict: True` flag is used, this does not remove existing values.

    Options in sysconfig file not specified in `options` dict
    will be untouched, unless `strict: True` flag is used.

    Changes dict will contain the list of changes made.
    '''
    return _options_ops('present', name, options, separator, field_separator, strict)

def options_absent(name, options={}, separator='=', field_separator=' '):
    '''
    .. code-block:: yaml

      /home/saltminion/sysconfig:
        sysconfig.options_absent:
          - separator: '='
          - options:
              test: 'testval'
              test:
                - 'val1'
                - 'val2'
              test2: 'testvalA testvalB'

    This makes sure specified values are not present in given sysconfig
    file for specified keys.
    Values can be provided either as a list of strings or single string.

    Keys are never removed. When last value is removed, key is left with
    empty string as a value.

    Options in sysconfig file not specified in `options` dict
    will be untouched.

    Changes dict will contain the list of changes made.
    '''
    return _options_ops('absent', name, options, separator, field_separator, False)
