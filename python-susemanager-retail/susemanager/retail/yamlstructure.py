#!/usr/bin/python
import yaml
import logging
from .branch import Branch, list_branch_servers
from .hwtypes import HWtypes
from .statistics import statistics

log = logging.getLogger(__name__)

class YAMLstructure:
    """ load and save SUSE Manager for Retail configuration as yaml file """
    def __init__(self):
        self.yaml = {
            'branches': {},
            'hwtypes': {}
        }

    def loadFile(self, name):
        """ load configuration from yaml file """
        with open(name, 'r') as infile:
            self.yaml = yaml.safe_load(infile)
            if not isinstance(self.yaml, dict):
                raise RuntimeError("invalid yaml file '{}'".format(name))

    def saveFile(self, name):
        """ save onfiguration as yaml file """
        with open(name, 'w') as outfile:
            yaml.safe_dump(self.yaml, outfile, default_flow_style=False)

    def upload(self, client, key, only_branch=None, only_new=False):
        """ upload configuration to SUSE Manager API"""

        statistics.add_counters(["Servers added", "Servers updated", "HWTYPEs added", "HWTYPEs updated", "Terminals added", "Terminals updated"])

        # hwtype groups must be created first, terminal entries may rely on them
        hwtypes = HWtypes()
        hwtypes.connect(client, key)
        hwtypes.from_yaml(self.yaml.get('hwtypes', {}))

        if only_branch is None:
            branch_server_id_list = self.yaml.get('branches', {}).keys()
        else:
            branch_server_id_list = [only_branch]

        hwAddress_dict = {}

        branches = []
        for branch_server_id in branch_server_id_list:
            if branch_server_id not in self.yaml.get('branches', {}):
                raise RuntimeError("specified branch {} is not in yaml".format(branch_server_id))
            branch_yaml = self.yaml.get('branches', {}).get(branch_server_id, {})
            branch = Branch(branch_server_id, branch_yaml.get('hwAddress'))
            if branch.connect(client, key):
                try:
                    branch.from_yaml(branch_yaml, hwAddress_dict=hwAddress_dict)
                    branches.append(branch)
                except:
                    log.error("Configuration of Branch {} failed:".format(branch_server_id))
                    raise
            else:
                log.warning("'%s' does not exist, skipping.", branch_server_id)

        # hwtype groups must be created first, terminal entries may rely on them
        hwtypes.upload(only_new=only_new)
        hwtypes.disconnect()
        for branch in branches:
                branch.upload(only_new=only_new)
                branch.disconnect()


    def download(self, client, key):
        """ download configuration from SUSE Manager API"""
        for branch_server_id in list_branch_servers(client, key):
            branch = Branch(branch_server_id)
            branch.connect(client, key)
            self.yaml['branches'][branch_server_id] = branch.to_yaml()
            branch.disconnect()

        hwtypes = HWtypes()
        hwtypes.connect(client, key)
        self.yaml['hwtypes'] = hwtypes.to_yaml()
        hwtypes.disconnect()
