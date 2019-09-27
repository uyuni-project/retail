#!/usr/bin/python
import logging
import tempfile

log = logging.getLogger()
_log_file = None

LOG_LEVEL_STRINGS = ['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG']
def log_level_string_to_int(log_level_string):
    if not log_level_string in LOG_LEVEL_STRINGS:
        message = 'invalid choice: {0} (choose from {1})'.format(log_level_string, LOG_LEVEL_STRINGS)
        raise argparse.ArgumentTypeError(message)
    log_level_int = getattr(logging, log_level_string, logging.INFO)

    return log_level_int



def init_logging(level, name="retail", logfile=None):
    log.setLevel(logging.DEBUG)
    stderr_handler = logging.StreamHandler()
    stderr_handler.setLevel(level)
    log.addHandler(stderr_handler)

    if (logfile is None):
        d = tempfile.mkdtemp(prefix=name + '_')
        logfile = d + '/' + name

    file_handler =  logging.FileHandler(logfile)
    file_handler.setLevel(logging.DEBUG) # all messages

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)

    log.addHandler(file_handler)
    global _log_file
    _log_file = logfile
    log.info("{} started with log level {}".format(name, logging.getLevelName(level)))

def print_logfile_info():
    log.warn("Log saved to file {}".format(_log_file))
