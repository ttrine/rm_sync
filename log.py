import logging
from logging.handlers import BufferingHandler
import os

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

    def shouldFlush(self, record: logging.LogRecord) -> bool:
        """ Only flush at the end of the script's execution, *if* there was an error. """
        if record.msg != "Update complete":
            return False
        return any([record.levelname == 'ERROR' for record in self.buffer])
