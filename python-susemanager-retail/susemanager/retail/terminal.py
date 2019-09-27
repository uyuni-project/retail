import logging
from .api import log_duplicate_system
from .statistics import statistics
try:
    import xmlrpc.client as xmlrpc_client
except ImportError:
    import xmlrpclib as xmlrpc_client

log = logging.getLogger(__name__)


class Terminal:
    """ handle mapping between high-level configuration and terminal entry"""

    def __init__(self, branch_prefix, hostname=None, hwAddress=None, system_id=None):
        self.branch_prefix = branch_prefix
        self.hostname = hostname
        self.hwAddress = hwAddress
        if hwAddress:
            self.hwAddress = hwAddress.lower()
        else:
            self.hwAddress = None
        self.ip = None
        self.formulas = {}
        self.hwtype = None
        self.system_id = system_id

    def connect(self, client, key):
        """ connect to API """
        self.client = client
        self.key = key

    def upload(self, only_new=False):
        if not self.system_id:
            try:
                self.client.system.createSystemProfile(self.key, self.branch_prefix + '.' + self.hostname, {'hwAddress': self.hwAddress})
            except xmlrpc_client.Fault as e:
                if not log_duplicate_system(log, self.client, self.key, e,
                    "Can't create terminal '{}'. A system with hwAddress '{}' already exists:".format(self.branch_prefix + '.' + self.hostname, self.hwAddress)):
                    raise e
                return False

            ids = self.client.system.getId(self.key, self.branch_prefix + '.' + self.hostname)
            if not isinstance(ids, list) or len(ids) == 0:
                log.error("Could not create '%s'", self.branch_prefix + '.' + self.hostname)
                return False

            self.system_id = ids[0]['id']
            statistics.inc("Terminals added")
            log.debug("Terminal added: " + self.branch_prefix + '.' + self.hostname)
        else:
            if only_new:
                return False
            statistics.inc("Terminals updated")
            log.debug("Terminal updated: " + self.branch_prefix + '.' + self.hostname)

        self.client.systemgroup.addOrRemoveSystems(self.key, self.branch_prefix, [self.system_id], True)
        self.client.systemgroup.addOrRemoveSystems(self.key, "TERMINALS", [self.system_id], True)
        if self.hwtype is not None:
            self.client.systemgroup.addOrRemoveSystems(self.key, 'HWTYPE:' + self.hwtype, [self.system_id], True)

        enabled_formulas = set(self.client.formula.getFormulasByServerId(self.key, self.system_id))
        enabled_formulas.update(self.formulas.keys())
        enabled_formulas = list(enabled_formulas)

        self.client.formula.setFormulasOfServer(self.key, self.system_id, enabled_formulas)
        for f in self.formulas:
            self.client.formula.setSystemFormulaData(self.key, self.system_id, f, self.formulas[f])
        return True

    def download(self):
        try:
            self.hostname = self.client.system.getNetwork(self.key, self.system_id)['hostname']
            if not self.hostname or self.hostname == '(none)':
                raise ValueError()
        except:
            self.hostname = self.client.system.getName(self.key, self.system_id)['name']

        if self.hostname.startswith(self.branch_prefix + '.'):
            self.hostname = self.hostname[len(self.branch_prefix) + 1 : ]
        dotpos = self.hostname.find('.')
        if dotpos != -1:
            self.hostname = self.hostname[:dotpos]

        net_devices = self.client.system.getNetworkDevices(self.key, self.system_id)
        for nic in net_devices:
            if nic.get('interface') != 'lo' and nic.get('hardware_address'):
                self.hwAddress = nic.get('hardware_address')
                if self.hwAddress:
                    self.hwAddress = self.hwAddress.lower()
                self.ip = nic.get('ip')
                break

        self.formulas = {}
        enabled_formulas = set(self.client.formula.getFormulasByServerId(self.key, self.system_id))
        for f in enabled_formulas:
            self.formulas[f] = self.client.formula.getSystemFormulaData(self.key, self.system_id, f)

        groups = self.client.system.listGroups(self.key, self.system_id)
        for g in groups:
            if g.get('system_group_name', '').startswith('HWTYPE:') and g.get('subscribed'):
                self.hwtype = g['system_group_name'][len('HWTYPE:') : ]
                break


    def from_yaml(self, yaml):
        """ configure terminal from yaml structure """
        self.hwAddress = yaml.get('hwAddress')
        if self.hwAddress:
            self.hwAddress = self.hwAddress.lower()
        self.ip = yaml.get('IP')
        self.formulas = {}
        for f in yaml:
            if isinstance(yaml[f], dict):
                self.formulas[f] = yaml[f]

        self.hwtype = yaml.get('hwtype')

    def to_yaml(self):
        log.debug("Terminal to yaml: " + self.hostname)
        ret = { self.hostname: {'hwAddress': self.hwAddress }}
        if self.ip:
            ret[self.hostname]['IP'] = self.ip
        if self.hwtype:
            ret[self.hostname]['hwtype'] = self.hwtype
        ret[self.hostname].update(self.formulas)
        return ret
