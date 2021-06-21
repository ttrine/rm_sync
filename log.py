import logging


def set_up_logger(module):
    logger = logging.getLogger(module)
    logging.basicConfig(level=logging.INFO, format='%(message)s')

    # Need these to prevent unwanted output from PDF rendering package
    logging.getLogger('rmrl').setLevel(logging.WARNING)
    logging.getLogger('rmcl').setLevel(logging.WARNING)

    return logger
