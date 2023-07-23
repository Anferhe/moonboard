import logging
import string

X_GRID_NAMES = string.ascii_uppercase[0:11]


def position_trans(pos, num_rows: int):
    """convert led number (strip number) to moonboard grid """
    col = pos // num_rows
    row = (pos % num_rows) + 1

    if col % 2 == 1:
        row = (num_rows + 1) - row
    return X_GRID_NAMES[col] + str(row)


def decode_problem_string(s: str, flags: str):
    holds = {'START': [], 'MOVES': [], 'TOP': [], 'FLAGS': [flags]}

    num_rows = 18 if flags.find("M") == -1 else 12

    for h in s.split(','):
        type, position = h[0], position_trans(int(h[1:]), num_rows)
        if type == 'S':
            holds['START'].append(position)
        elif type == 'P':
            holds['MOVES'].append(position)
        elif type == 'E':
            holds['TOP'].append(position)

    return holds


class UnstuffSequence:
    """
    hold sequence come separated in parts due to BLE packet size limitation
    this class serves to put different parts together
    """

    START = 'l#'
    STOP = '#'

    def __init__(self, logger: logging.Logger = None):
        self.logger = logger if logger is not None else logging

        self.s: str = ''
        self.flags: str = ''
        self.started: bool  = False

    def process_bytes(self, ba: str):
        """ 
        process new incoming bytes and return if new problem is available. 
        handle some error due to multiple connected devices sending simoultaneously.
        """

        s = bytearray.fromhex(ba).decode()
        self.logger.debug("incoming bytes:" + str(s))

        if s[0] == '~' and s[-1] == '*':
            # Flag processing
            self.flags = s[1:-1]
            if s.find("M") != -1:
                self.logger.debug('MINI')
            if s.find("D") != -1:
                self.logger.debug('BothLights')
        elif s[:2] == self.START:
            self.logger.debug('START')
            if not self.started:
                if s[-1] == self.STOP:
                    return s[2:-1]
                else:
                    self.started = True
                    self.s = s[2:]
            else:
                self.logger.debug('error: alredy started')
                self.reset()
        elif s[-1] == self.STOP:
            self.logger.debug('STOP')
            if self.started:
                ret = self.s + s[:-1]
                self.reset()
                return ret
            else:
                self.logger.debug('error: not started')
                self.reset()
        else:
            if self.started:
                self.s += s

    def reset(self):
        self.s = ''
        self.started = False
