# (c) 2022 The MITRE Corporation, All Rights Reserved
import logging
import sys

root_formatter = logging.Formatter('%(levelname)s: %(msg)s')
root_log_handler = logging.StreamHandler()
root_log_handler.setFormatter(root_formatter)
root_logger = logging.getLogger()
root_logger.addHandler(root_log_handler)
root_logger.setLevel(logging.INFO)


# Logger that prints to stdout with name prefixed
def make_stdout_logger(name: str, level):
    formatter = logging.Formatter(fmt='{name}: {message}', style='{')
    channel = logging.StreamHandler(sys.stdout)
    channel.setLevel(level)
    channel.setFormatter(formatter)
    lg = logging.getLogger(name)
    lg.addHandler(channel)
    return lg


def debug_action(pattern: str, k: str, data: str):
    logging.debug(f'main(): action "{k}" matches "{pattern}" {data}')
