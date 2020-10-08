#!/usr/bin/python
import netaddr
import re
import json
import logging
try:
    import xmlrpc.client as xmlrpc_client
except ImportError:
    import xmlrpclib as xmlrpc_client

from .groups import Groups
from .terminal import Terminal
from .statistics import statistics
from .api import log_duplicate_system

log = logging.getLogger(__name__)


SRV_DIRECTORY = '/srv/saltboot'
SRV_DIRECTORY_GROUP = 'saltboot'
SRV_DIRECTORY_USER = 'saltboot'

def list_branch_servers(client, key):
    systems = client.systemgroup.listSystemsMinimal(key, 'SERVERS')
    systems = [s['name'] for s in  systems]
    return systems

class Branch:
    """ handle mapping between high-level configuration and branch formulas"""

    def __init__(self, branch_server_id, hwAddress=None):
        self.branch_server_id = branch_server_id
        # disabled formulas are set to None
        self.formulas = {
            'branch-network': { # formula name
                'branch_network': { # pillar entry, can differ from forrmula name
                    'srv_directory': SRV_DIRECTORY,
                    'srv_directory_group': SRV_DIRECTORY_GROUP,
                    'srv_directory_user': SRV_DIRECTORY_USER,
                },
                'pxe': {}
            },
            'dhcpd': None, # optional
            'bind': {},
            'tftpd': {},
            'vsftpd': {},
            'pxe': {}
        }
        self.groups = Groups()

        # Make sure these groups allways exist
        self.groups.add('SERVERS', 'All servers')
        self.groups.add('TERMINALS', 'All terminals')
        self.client = None
        self.key = None
        self.bs_system_id = None
        self.bs_net_devices = None
        self.branch_prefix = None
        if hwAddress:
            self.hwAddress = hwAddress.lower()
        else:
            self.hwAddress = None
        self.terminals = []
        self.exclude_formulas = []

    def configure_dedicated_nic(self, nic, ip='192.168.1.1', netmask='255.255.255.0', configure_firewall=True, firewall=None):
        """ configure branch network for dedicated NIC """
        self.formulas['branch-network']['branch_network'] = {
            'configure_firewall': configure_firewall,
            'dedicated_NIC': True,
            'firewall': {
                'enable_NAT': True,
                'enable_route': True,
                'open_ssh_port': True,
                'open_xmpp_server_port': True,
                'open_xmpp_client_port': True
            },
            'forwarder': 'bind',
            'forwarder_fallback': True,
            'ip': ip,
            'netmask': netmask,
            'nic': nic,
            'srv_directory': SRV_DIRECTORY,
            'srv_directory_group': SRV_DIRECTORY_GROUP,
            'srv_directory_user': SRV_DIRECTORY_USER
        }
        if firewall:
            # override default
            self.formulas['branch-network']['branch_network']['firewall'] = firewall


    def configure_default_nic(self, configure_firewall=True, firewall=None):
        """ configure branch network for default NIC """
        self.formulas['branch-network']['branch_network'] = {
            'configure_firewall': configure_firewall,
            'dedicated_NIC': False,
            'firewall': {
                'open_dhcp_port': True,
                'open_dns_port': True,
                'open_ftp_port': True,
                'open_tftp_port': True,
                'open_http_port': True,
                'open_https_port': True,
                'open_salt_ports': True,
                'open_ssh_port': True,
                'open_xmpp_server_port': True,
                'open_xmpp_client_port': True
            },
            'srv_directory': SRV_DIRECTORY,
            'srv_directory_group': SRV_DIRECTORY_GROUP,
            'srv_directory_user': SRV_DIRECTORY_USER
        }
        if firewall:
            # override default
            self.formulas['branch-network']['branch_network']['firewall'] = firewall

    def configure_pxe(self, branch, kernel_parameters=None, kernel_parameters_append=False):
        """ configure PXE formula """

        default_kernel_parameters = 'panic=60 ramdisk_size=710000 ramdisk_blocksize=4096 vga=0x317 splash=silent'
        if kernel_parameters is None:
            kernel_parameters = default_kernel_parameters
        else:
            if kernel_parameters_append:
                kernel_parameters = '{} {}'.format(default_kernel_parameters, kernel_parameters)

        self.formulas['branch-network']['pxe']['branch_id'] = self.branch_prefix
        self.formulas['pxe'] = {
            'pxe': {
                'default_kernel_parameters': kernel_parameters,
                'initrd_name': 'initrd',
                'kernel_name': 'linux',
                'pxe_root_directory': SRV_DIRECTORY
            }
        }
        self.groups.add(self.branch_prefix, "Group for branch {}".format(branch))

    def configure_dhcp(self, domain, nic=None, ip=None, netmask=None, dyn_range=['192.168.1.10', '192.168.1.250'], terminals=[]):
        """ configure DHCPD formula """
        if not nic:
            nic = self.formulas.get('branch-network', {}).get('branch_network', {}).get('nic')
        if not nic:
            # no dedicated nic, so there should be only one
            for known_nic in self.bs_net_devices:
                if known_nic.get('interface') != 'lo' and known_nic.get('ip') and known_nic.get('netmask'):
                    if not ip:
                        ip = known_nic.get('ip')
                    if not netmask:
                        netmask = known_nic.get('netmask')
                    nic = known_nic.get('interface')
                    break

        if not nic:
            raise RuntimeError("nic is required for DHCP configuration")

        if not ip:
            ip = self.formulas['branch-network']['branch_network']['ip']

        if not netmask:
            netmask = self.formulas['branch-network']['branch_network']['netmask']

        network = netaddr.IPNetwork(ip + '/' + netmask)

        self.formulas['dhcpd'] = {
            'dhcpd': {
                'default_lease_time': 20000,
                'max_lease_time': 20001,
                'domain_name': domain,
                'domain_name_servers': [ip],
                'listen_interfaces': [nic],
                'hosts': {},
                'subnets': {
                    str(network.network): {
                        'broadcast_address': str(network.broadcast),
                        'filename': '/boot/pxelinux.0',
                        'filename_efi': 'boot/grub.efi',
                        'netmask': netmask,
                        'next_server': ip,
                        'range': dyn_range,
                        'routers': [ip],
                        'hosts': {}
                    }
                }
            }
        }
        for t in terminals:
            if t.ip and t.hwAddress:
                self.formulas['dhcpd']['dhcpd']['subnets'][str(network.network)]['hosts'][t.hostname] = {
                    'fixed_address': t.ip,
                    'hardware': 'ethernet ' + t.hwAddress
                }


    def configure_tftpd(self):
        """ configure TFTP formula """
        dedicated_nic = self.formulas.get('branch-network', {}).get('branch_network', {}).get('dedicated_NIC', False)
        if dedicated_nic:
            ip = self.formulas['branch-network']['branch_network']['ip']
        else:
            ip = '0.0.0.0'
 
        self.formulas['tftpd'] = {
            'tftpd': {
                'listen_ip': ip,
                'root_dir': SRV_DIRECTORY,
                'tftpd_user': SRV_DIRECTORY_USER
            }
        }


    def configure_vsftpd(self):
        """ configure vsftpd formula """
        dedicated_nic = self.formulas.get('branch-network', {}).get('branch_network', {}).get('dedicated_NIC', False)
        if dedicated_nic:
            ip = self.formulas['branch-network']['branch_network']['ip']
        else:
            ip = '0.0.0.0'
 
        self.formulas['vsftpd'] = {

            'vsftpd_config': {
                'anon_root': SRV_DIRECTORY,
                'listen_address': ip,
                'ssl_enable': False,
                'secure_chroot_dir': '/usr/share/empty',
                'anonymous_enable': True,
                'allow_anon_ssl': True,
                'listen': True,
                'local_enable': True,
                'dirmessage_enable': True,
                'use_localtime': True,
                'xferlog_enable': True,
                'connect_from_port_20': True,
                'pam_service_name': 'vsftpd',
                'rsa_cert_file': '/etc/ssl/certs/[ssl-cert-file].pem',
                'rsa_private_key_file': '/etc/ssl/private/[ssl-cert-file].key'
            }
        }

    def configure_bind(self, branch_server, domain, branch_ip = None, salt_cname = None, network = None, contact = None, options= None, terminals = []):
        """ configure bind formula """
        dedicated_nic = self.formulas.get('branch-network', {}).get('branch_network', {}).get('dedicated_NIC', False)
        if dedicated_nic:
            if network is None:
                branch_ip = self.formulas['branch-network']['branch_network']['ip']
                netmask = self.formulas['branch-network']['branch_network']['netmask']
                network = netaddr.IPNetwork(branch_ip + '/' + netmask)
            else:
                network = netaddr.IPNetwork(network)
        else:
            if network is None:
                for known_nic in self.bs_net_devices:
                    if known_nic.get('interface') != 'lo' and known_nic.get('ip') and known_nic.get('netmask'):
                        branch_ip = known_nic.get('ip')
                        netmask = known_nic.get('netmask')
                        network = netaddr.IPNetwork(branch_ip + '/' + netmask)
                        break
            else:
                network = netaddr.IPNetwork(network)

        if network is None:
            raise RuntimeError("IP/netmask not specified")

        rev_zone = network.ip.reverse_dns
        rev_zone = re.compile('^[^.]*\.').sub('', rev_zone)
        rev_zone = re.compile('\.$').sub('', rev_zone)

        if salt_cname is None:
            salt_cname = branch_server + '.' + domain
        if not salt_cname.endswith('.'):
            salt_cname = salt_cname + '.'

        if not options:
            options = { 'include_forwarders': True }

        self.formulas['bind'] = {
            'bind': {
                'config': options,
                'configured_zones': {
                    domain: {
                        'type': 'master',
                        'notify': False
                    },
                    rev_zone: {
                        'type': 'master',
                        'notify': False
                    }
                },
                'available_zones': {
                    domain: {
                        'file': domain + '.txt',
                        'soa': {
                            'ns': branch_server + '.' + domain,
                            'contact': contact,
                            'serial': 'auto',
                            'class': 'IN',
                            'refresh': 8600,
                            'retry': 900,
                            'expiry': 86000,
                            'nxdomain': 500,
                            'ttl': 8600
                        },
                        'records': {
                            'A': {
                                branch_server: branch_ip,
                            },
                            'NS': {
                                '@': [
                                    branch_server,
                                ]
                            },
                            'CNAME': {
                                'ftp': branch_server + '.' + domain + '.',
                                'tftp': branch_server + '.' + domain + '.',
                                'dns': branch_server + '.' + domain + '.',
                                'dhcp': branch_server + '.' + domain + '.',
                                'salt': salt_cname
                            }
                        },
                        'generate_reverse': {
                            'net': '',
                            'for_zones': []
                        }
                    },
                    rev_zone: {
                        'file': rev_zone + '.txt',
                        'soa': {
                            'ns': branch_server + '.' + domain,
                            'contact': contact,
                            'serial': 'auto',
                            'class': 'IN',
                            'refresh': 8600,
                            'retry': 900,
                            'expiry': 86000,
                            'nxdomain': 500,
                            'ttl': 8600
                        },
                        'records': {
                            'A': {},
                            'NS': {
                                '@': [
                                    branch_server + '.' + domain + '.'
                                ]
                            },
                            'CNAME': {}
                        },
                        'generate_reverse': {
                            'net': str(network),
                            'for_zones': [
                                domain
                            ]
                        }
                    }
                }
            }
        }

        hostname_re = re.compile('^([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9])$')
        for t in terminals:
            if t.ip:
                if not hostname_re.match(t.hostname):
                    log.warning("'%s' is not a valid hostname, skipping", t.hostname)
                    continue
                self.formulas['bind']['bind']['available_zones'][domain]['records']['A'][t.hostname] = t.ip

    def configure_branch_prefix(self, branch_prefix):
        self.branch_prefix = branch_prefix
        self.formulas['branch-network']['pxe']['branch_id'] = self.branch_prefix

    def configure_terminal_naming(self, terminal_naming = None):
        if terminal_naming is None:
            terminal_naming = {
                'minion_id_naming': 'Hostname',
                'disable_id_prefix': False,
                'disable_unique_suffix': False
            }
        self.formulas['branch-network']['pxe'] = terminal_naming
        self.formulas['branch-network']['pxe']['branch_id'] = self.branch_prefix

    def connect(self, client, key):
        """
        connect to SUSE Manager API and fetch branch server data used for dynamic defaults
        return True on success
               False if the system does not exist
        """
        self.client = client
        self.key = key

        ids = self.client.system.getId(self.key, self.branch_server_id)
        if not isinstance(ids, list):
            return False

        if len(ids) == 0:
            self.bs_system_id = None
            self.bs_net_devices = []

            return True


        self.bs_system_id = ids[0]['id']

        self.bs_net_devices = self.client.system.getNetworkDevices(self.key, self.bs_system_id)

        return True

    def disconnect(self):
        """ disconnect from SUSE Manager API """
        self.client = None

    def upload(self, only_new=False):
        """ upload branch configuration """

        existing_terminals = self._download_terminals()
        for t in self.terminals:
            t.system_id = existing_terminals.get(t.hwAddress)

        if self.bs_system_id is None:
            if self.hwAddress is None:
                data = { 'hostname': self.branch_server_id }
            else:
                data = { 'hwAddress': self.hwAddress }

            try:
                self.client.system.createSystemProfile(self.key, self.branch_server_id, data)
            except xmlrpc_client.Fault as e:
                log_duplicate_system(log, self.client, self.key, e, "Can't create Branch Server '{}'. A system with {} already exists:".format(self.branch_server_id, data))
                raise e

            ids = self.client.system.getId(self.key, self.branch_server_id)
            if not isinstance(ids, list) or len(ids) == 0:
                raise RuntimeError("Could not create '%s'", self.branch_server_id)
            self.bs_system_id = ids[0]['id']
            statistics.inc("Servers added")
            log.debug("Server added: " + self.branch_server_id)
        else:
            if only_new:
                for t in self.terminals:
                    t.connect(self.client, self.key)
                    t.upload(only_new=True)
                return
            else:
                statistics.inc("Servers updated")
                log.debug("Server updated: " + self.branch_server_id)


        # do not touch excluded formulas
        enabled_formulas = set(self.client.formula.getFormulasByServerId(self.key, self.bs_system_id))
        not_excluded = set(self.formulas.keys()).difference(self.exclude_formulas)
        enabled_formulas.update(not_excluded)

        disable_formulas = [f for f in not_excluded if self.formulas[f] is None]
        enabled_formulas.difference_update(disable_formulas)
        enabled_formulas = list(enabled_formulas)

        self.client.formula.setFormulasOfServer(self.key, self.bs_system_id, enabled_formulas)
        for formula in not_excluded:
            if self.formulas[formula] is not None:
                self.client.formula.setSystemFormulaData(self.key, self.bs_system_id, formula, self.formulas[formula])


        self.groups.upload(self.client, self.key)
        self.client.systemgroup.addOrRemoveSystems(self.key, "SERVERS", [self.bs_system_id], True)
        if self.branch_prefix:
            self.client.systemgroup.addOrRemoveSystems(self.key, self.branch_prefix, [self.bs_system_id], True)

        for t in self.terminals:
            t.connect(self.client, self.key)
            t.upload()

    def _download_terminals(self):
        res = {}
        try:
            self.groups.download(self.client, self.key)
            branch_prefix_id = self.groups.get_id(self.branch_prefix)
            systems = self.client.systemgroup.listSystems(self.key, self.branch_prefix)
        except:
            return res

        for s in systems:
            sysid = s['id']
            net_devices = self.client.system.getNetworkDevices(self.key, sysid)
            for nic in net_devices:
                if nic.get('interface') != 'lo' and nic.get('hardware_address'):
                    res[nic.get('hardware_address').lower()] = sysid
        return res

    def download(self):
        """ download branch configuration """
        if self.bs_system_id is None:
            raise RuntimeError("Branch server '%s' does not exist", self.branch_server_id)

        enabled_formulas = set(self.client.formula.getFormulasByServerId(self.key, self.bs_system_id))
        self.exclude_formulas = []
        for formula in self.formulas:
            if formula in enabled_formulas:
                self.formulas[formula] = self.client.formula.getSystemFormulaData(self.key, self.bs_system_id, formula)
            else:
                self.formulas[formula] = None
                self.exclude_formulas.append(formula)

        try:
            branch_prefix = self.formulas['branch-network']['pxe']['branch_id']
            self.branch_prefix = branch_prefix
        except:
            raise RuntimeError("Branch server '%s' does not have Branch ID set in Branch Network form", self.branch_server_id)


        self.terminals = []
        systems = self.client.systemgroup.listSystems(self.key, branch_prefix)
        for s in systems:
            sysid = s['id']
            if sysid == self.bs_system_id:
                continue
            to = Terminal(branch_prefix, s.get('hostname') or s.get('profile_name'), system_id=sysid)
            to.connect(self.client, self.key)
            to.download()
            self.terminals.append(to)

    def from_yaml(self, yaml, hwAddress_dict={}):
        """ configure branch server from yaml structure """

        server_name = yaml.get('server_name')
        server_domain = yaml.get('server_domain')
        branch_prefix = yaml.get('branch_prefix')
        self.exclude_formulas = yaml.get('exclude_formulas', [])

        if server_name is None:
            server_name = re.compile('\..*$').sub('', self.branch_server_id)

        if server_domain is None:
            server_domain = re.compile('^[^.]*\.').sub('', self.branch_server_id)

        if branch_prefix is None:
            branch_prefix = re.compile('\..*$').sub('', server_domain)
        self.branch_prefix = branch_prefix

        salt_cname = yaml.get('salt_cname')
        contact = yaml.get('contact')

        bind_options = yaml.get('configure_bind_options')

        self.terminals = []

        for t in yaml.get('terminals', {}).keys():
            to = Terminal(branch_prefix, t)
            to.from_yaml(yaml.get('terminals', {}).get(t))
            self.terminals.append(to)
            if to.hwAddress in hwAddress_dict:
                raise RuntimeError("Duplicate hwAddress {} for {}, {}".format(to.hwAddress, to.hostname, hwAddress_dict[to.hwAddress]))
            else:
                hwAddress_dict[to.hwAddress] = to.hostname

        nic = yaml.get('nic')
        dedicated_nic = yaml.get('dedicated_nic')
        dyn_range = yaml.get('dyn_range', ['192.168.1.10', '192.168.1.250'])

        if dedicated_nic:
            branch_ip = yaml.get('branch_ip', '192.168.1.1')
            netmask = yaml.get('netmask', '255.255.255.0')

            self.configure_dedicated_nic(nic, ip=branch_ip, netmask=netmask, configure_firewall=yaml.get('configure_firewall', True), firewall=yaml.get('firewall'))
            self.configure_dhcp(server_domain, nic=nic, ip=branch_ip, netmask=netmask, dyn_range=dyn_range, terminals=self.terminals)
            self.configure_bind(server_name, server_domain, branch_ip=branch_ip, salt_cname=salt_cname, contact=contact, options=bind_options, terminals=self.terminals)
        else:
            branch_ip = yaml.get('branch_ip')
            netmask = yaml.get('netmask', '255.255.255.0')

            self.configure_default_nic(configure_firewall=yaml.get('configure_firewall', True), firewall=yaml.get('firewall'))
            if 'dhcpd' not in self.exclude_formulas:
                self.configure_dhcp(server_domain, nic=nic, ip=branch_ip, netmask=netmask, dyn_range=dyn_range, terminals=self.terminals)
            self.configure_bind(server_name, server_domain, branch_ip=branch_ip, salt_cname=salt_cname, contact=contact, options=bind_options, terminals=self.terminals)

        self.configure_terminal_naming(yaml.get('terminal_naming'))
        self.configure_vsftpd()
        self.configure_tftpd()
        self.configure_pxe(server_domain, yaml.get('default_kernel_parameters'))
        self.hwAddress = yaml.get('hwAddress')
        if self.hwAddress:
            self.hwAddress = self.hwAddress.lower()
            if self.hwAddress in hwAddress_dict:
                raise RuntimeError("Duplicate hwAddress {} for {}, {}".format(self.hwAddress, self.branch_server_id, hwAddress_dict[self.hwAddress]))
            else:
                hwAddress_dict[self.hwAddress] = self.branch_server_id


    def to_yaml(self):
        """ download formula data and return corresponding yaml structure """
        log.debug("Server to yaml: " + self.branch_server_id)
        self.download()

        server_domain = None
        if self.formulas['dhcpd']:
            server_domain = self.formulas['dhcpd'].get('dhcpd', {}).get('domain_name')

        if server_domain is None:
            for domain in self.formulas['bind'].get('bind', {}).get('available_zones', {}):
                if not domain.endswith('in-addr.arpa'):
                    server_domain = domain
                    break
        server_name = self.formulas['bind'].get('bind', {}).get('available_zones', {}).get(server_domain, {}).get('records', {}).get('NS', {}).get('@', [''])[0]
        terminal_naming = self.formulas['branch-network'].get('pxe')
        branch_prefix = terminal_naming.pop('branch_id')

        dedicated_nic = self.formulas['branch-network'].get('branch_network', {}).get('dedicated_NIC', False)
        yaml = {
            'server_name': server_name,
            'server_domain': server_domain,
            'branch_prefix': branch_prefix,
            'dedicated_nic': dedicated_nic
        }
        yaml['terminal_naming'] = terminal_naming

        if dedicated_nic:
            yaml['nic'] = self.formulas['branch-network'].get('branch_network', {}).get('nic', False)
            yaml['branch_ip'] = self.formulas['branch-network'].get('branch_network', {}).get('ip', '')
            yaml['netmask'] = self.formulas['branch-network'].get('branch_network', {}).get('netmask', '')
            if self.formulas['dhcpd']:
                try:
                    network = netaddr.IPNetwork(yaml['branch_ip'] + '/' + yaml['netmask'])
                    yaml['dyn_range'] = self.formulas['dhcpd'].get('dhcpd', {}).get('subnets', {}).get(str(network.network), {}).get('range')
                except:
                    pass
        else:
            # no dedicated nic, so there should be only one
            for known_nic in self.bs_net_devices:
                if known_nic.get('interface') != 'lo' and known_nic.get('ip') and known_nic.get('netmask'):
                    yaml['branch_ip'] = known_nic.get('ip')
                    yaml['netmask'] = known_nic.get('netmask')
                    yaml['nic'] = known_nic.get('interface')
                    break
            if self.formulas['dhcpd']:
                try:
                    network = netaddr.IPNetwork(yaml['branch_ip'] + '/' + yaml['netmask'])
                    yaml['dyn_range'] = self.formulas['dhcpd'].get('dhcpd', {}).get('subnets', {}).get(str(network.network), {}).get('range')
                except:
                    pass

        yaml['configure_firewall'] = self.formulas['branch-network'].get('branch_network', {}).get('configure_firewall', False)
        if yaml['configure_firewall']:
            yaml['firewall'] = self.formulas['branch-network'].get('branch_network', {}).get('firewall', {})

        yaml['configure_bind_options'] = self.formulas['bind'].get('bind', {}).get('config', {})

        yaml['salt_cname'] = self.formulas['bind'].get('bind', {}).get('available_zones', {}).get(server_domain, {}).get('records', {}).get('CNAME', {}).get('salt')
        if yaml['salt_cname'] and yaml['salt_cname'].endswith('.'):
            yaml['salt_cname'] = yaml['salt_cname'][:-1]
        if self.hwAddress is not None:
            yaml['hwAddress'] = self.hwAddress

        yaml['default_kernel_parameters'] = self.formulas['pxe'].get('pxe', {}).get('default_kernel_parameters', '')

        if len(self.terminals) > 0:
            yaml['terminals'] = {}
            for t in self.terminals:
                yaml['terminals'].update(t.to_yaml())

        if len(self.exclude_formulas) > 0:
            yaml['exclude_formulas'] = self.exclude_formulas

        return yaml

