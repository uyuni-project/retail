#!/usr/bin/python
import logging
log = logging.getLogger(__name__)

class Groups(object):
    """ keep track of existing and wanted groups """

    _existing_groups = None

    def get_existing_groups(self):
        return type(self)._existing_groups

    def set_existing_groups(self, val):
        type(self)._existing_groups = val

    existing_groups = property(get_existing_groups, set_existing_groups)

    def __init__(self):
        self.groups = {}  # wanted groups

    def add(self, name, desc):
        """ add wanted group """
        self.groups[name] = desc

    def download(self, client, key, force=False):
        """ update list of existing groups from SUSE Manager API """
        if self.existing_groups is None or force:
            log.debug("Downloading existing groups")
            existing_groups = client.systemgroup.listAllGroups(key)
            self.existing_groups = {g['name'] : g for g in existing_groups}

    def upload(self, client, key):
        """ create all wanted groups in SUSE Manager API, returns dictionary with new groups """
        self.download(client, key)
        ret = {}

        for group, desc in self.groups.items():
            if group not in self.existing_groups:
                log.debug("Creating group " + group)
                client.systemgroup.create(key, group, desc)
                self.existing_groups[group] = client.systemgroup.getDetails(key, group)
                ret[group] = desc
        return ret

    def get_attr(self, name, attr):
        """ get attribute of existing group """
        return self.existing_groups[name][attr]

    def get_id(self, name):
        """ get id of existing group """
        return self.get_attr(name, 'id')

    def get_existing(self):
        """ get list of existing groups """
        return self.existing_groups.keys()
