"""
susemanager.retail public API

Usage example:

    import susemanager.retail

    client, key = susemanager.retail.connect(args)

    branch = susemanager.retail.Branch(args.branch_name)
    if not branch.connect(client, key):
        sys.exit(1)

    branch.configure_dedicated_nic(args.dedicated_nic, ip=args.branch_ip, netmask=args.netmask)
    branch.configure_dhcp(args.server_domain, dyn_range=args.dyn_range)
    branch.configure_bind(args.server_name, args.server_domain, branch_ip=args.branch_ip, salt_cname=args.salt_cname, contact=args.contact)

    branch.configure_vsftpd()
    branch.configure_tftpd()
    branch.configure_pxe(args.server_domain, args.branch_prefix)

    branch.upload()

    hwtypes = susemanager.retail.HWtypes()
    hwtypes.connect(client, key)
    hwtypes.from_yaml({
      'TOSHIBA-6140100': {
        'description': 'HWTYPE group for TOSHIBA-6140100',
        'saltboot': partitioning_data
      }
    })
    hwtypes.upload()


"""
from .branch import Branch
from .hwtypes import HWtypes
from .yamlstructure import YAMLstructure
from .api import connect
from .statistics import statistics