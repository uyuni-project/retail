#!/usr/bin/python
import json
import logging
from .groups import Groups
from .statistics import statistics

log = logging.getLogger(__name__)

class HWtypes:
    """ manage configuration for hardware types """
    def __init__(self):
        self.groups = Groups() # hwtype groups
        self.hwtypes = {}      # group formulas
        self.client = None
        self.key = None

    def add(self, hw_name, desc, formulas):
        """ add new entry for hwtype group with corresponding formulas """
        self.hwtypes[hw_name] = formulas
        self.groups.add("HWTYPE:" + hw_name, desc)

    def connect(self, client, key):
        """ connect to API """
        self.client = client
        self.key = key

    def disconnect(self):
        """ disconnect from API """
        self.client = None

    def upload(self, only_new=False):
        """ upload grups and group formulas to API """
        created_groups = self.groups.upload(self.client, self.key)

        for hw_name in self.hwtypes:
            group = "HWTYPE:" + hw_name
            if only_new and group not in created_groups:
                continue
            group_id = self.groups.get_id(group)
            enabled_formulas = set(self.client.formula.getFormulasByGroupId(self.key, group_id))
            enabled_formulas.update(self.hwtypes[hw_name].keys())
            enabled_formulas = list(enabled_formulas)

            self.client.formula.setFormulasOfGroup(self.key, group_id, enabled_formulas)
            for formula in self.hwtypes[hw_name]:
                self.client.formula.setGroupFormulaData(self.key, group_id, formula, self.hwtypes[hw_name][formula])
            if group not in created_groups:
                statistics.inc("HWTYPEs updated")
                log.debug("HWTYPE updated: " + group)
            else:
                statistics.inc("HWTYPEs added")
                log.debug("HWTYPE added: " + group)

    def download(self):
        """ download hwtype groups and group formulas from API """

        self.groups.download(self.client, self.key)
        groups = self.groups.get_existing()

        for group in groups:
            group_id = self.groups.get_id(group)
            if group.startswith("HWTYPE:"):
                hw_name = group[len("HWTYPE:"):]
                formulas = {}
                for formula in self.client.formula.getFormulasByGroupId(self.key, group_id):
                    formulas[formula] = self.client.formula.getGroupFormulaData(self.key, group_id, formula)
                self.add(hw_name, self.groups.get_attr(group, "description"), formulas)

    def from_yaml(self, yaml):
        """ add group entries and corresponding saltboot formulas defined in yaml structure """
        for hw_name in yaml:
            formulas = {}
            for f in yaml[hw_name]:
                 if isinstance(yaml[hw_name][f], dict):
                     formulas[f] = yaml[hw_name][f]
            self.add(hw_name, yaml[hw_name].get("description", "Hardware group for {}".format(hw_name)), formulas)

    def to_yaml(self):
        """ download hwtype groups and group formulas from API and return them as yaml structure """
        log.debug("HwTypes to yaml")
        self.download()

        yaml = {}

        for hw_name in self.hwtypes:
            group = "HWTYPE:" + hw_name
            yaml[hw_name] = {
                'description': self.groups.get_attr(group, "description")
            }
            yaml[hw_name].update(self.hwtypes[hw_name])
        return yaml
