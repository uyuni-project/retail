#!/usr/bin/python
import getpass
import re
try:
    import xmlrpc.client as xmlrpc_client
except ImportError:
    import xmlrpclib as xmlrpc_client

def connect(args):
    """
    connect to SUSE Manager API using standard args

    args should be created this way:
        parser = argparse.ArgumentParser(description='...')
        parser.add_argument('--api-host', default='localhost', help='API host')
        parser.add_argument('--api-user', default='admin', help='API user')
        parser.add_argument('--api-pass', help='API password')
        args = parser.parse_args()

    return client, key

    client - xmlrpc_client object
    key - passed as first arg to API calls

    On error an suitable exception is raised.
    """
    if args.api_pass is None:
        args.api_pass = getpass.getpass("Password for SUSE Manager API user {} on {}: ".format(args.api_user, args.api_host))

    url = 'http://' + args.api_host + '/rpc/api'
    client = xmlrpc_client.Server(url, verbose=0, allow_none=True)
    key = client.auth.login(args.api_user, args.api_pass)
    return client, key

def log_duplicate_system(log, client, key, exception, msg):
    if exception.faultCode != 1100:
        return False
    match = re.search('Existing system IDs: \[([\s,0-9]+)\]', exception.faultString)
    if match:
        ids = [int(x) for x in re.split('\s*,\s*', match.group(1))]
        log.error(msg)
        for i in ids:
            system = client.system.getName(key, i)['name']
            log.error("  existing system: '{}'".format(system))
        return True

    return False
