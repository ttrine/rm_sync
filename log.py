import logging
from logging.handlers import BufferingHandler
import os
import pickle as pkl

MAILHOST = os.environ['MAILHOST']
FROMADDR = os.environ['FROMADDR']
TOADDRS = os.environ['TOADDRS'].split(' ')


def set_up_logger(module):
    logger = logging.getLogger(module)

    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-5s %(message)s')

    smtp_handler = BufferingSMTPHandler(mailhost=MAILHOST,
                                        fromaddr=FROMADDR,
                                        toaddrs=TOADDRS,
                                        subject='RM Sync Error')

    logger.addHandler(smtp_handler)

    # Need these to prevent unwanted output from PDF rendering package
    logging.getLogger('rmrl').setLevel(logging.WARNING)
    logging.getLogger('rmcl').setLevel(logging.WARNING)

    return logger


class BufferingSMTPHandler(BufferingHandler):
    def __init__(self, mailhost, fromaddr, toaddrs, subject):
        # Set 'capacity' to 0 since our overridden shouldFlush doesn't use it
        BufferingHandler.__init__(self, 0)
        self.mailhost = mailhost
        self.mailport = None
        self.fromaddr = fromaddr
        self.toaddrs = toaddrs
        self.subject = subject
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)-5s %(message)s"))

    def flush(self):
        if len(self.buffer) > 0:
            try:
                import smtplib
                port = self.mailport
                if not port:
                    port = smtplib.SMTP_PORT
                smtp = smtplib.SMTP(self.mailhost, port)
                msg = '''From: {}\r\nTo: {}\r\nSubject: {}\r\n\r\n'''.format(
                            self.fromaddr,
                            ",".join(self.toaddrs),
                            self.subject
                            )
                msg = msg + "An error occurred while syncing your Remarkable contents.\r\n" \
                            "Here is the full execution log:\r\n\r\n"
                for record in self.buffer:
                    s = self.format(record)
                    msg = msg + s + "\r\n"
                msg = msg.encode("ascii", "ignore")
                smtp.sendmail(self.fromaddr, self.toaddrs, msg)
                smtp.quit()
            except Exception as e:
                print(e)
                self.handleError(None)  # no particular record

            self.buffer = []

    def write_errors(self):
        """ Write errors in the buffer to a file outside of flush for comparison to the subsequent run. """
        with open(".prev_errs", 'wb') as f:
            pkl.dump(([record for record in self.buffer if record.levelname == 'ERROR']), f)

    def shouldFlush(self, record: logging.LogRecord) -> bool:
        """ Only flush at the end of the script's execution, *if* there was a new (previously unseen) error. """
        if record.msg != "Update complete":
            return False

        # On the last log statement, load up any errors from the previous run and compare with the current one.
        # If there are any new errors, flush. If not, don't. Either way, overwrite previous errors with current ones.
        curr_msgs = {record.msg for record in self.buffer if record.levelname == 'ERROR'}
        if os.path.exists('.prev_errs'):
            with open('.prev_errs', 'rb') as f:
                prev_errors = pkl.load(f)
            prev_msgs = {error.msg for error in prev_errors}
        else:
            prev_msgs = set()

        self.write_errors()

        return len(curr_msgs - prev_msgs) > 0
