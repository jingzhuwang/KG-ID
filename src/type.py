class Relation:
    def __init__(self, tarID, tarSig, cor):
        self.targetID = tarID
        self.targetSignal = tarSig
        self.type = cor


class Signal:
    def __init__(self, maxVal, minVal, rate):
        self.maxVal = maxVal
        self.minVal = minVal
        self.rate = rate
        self.rel: list[Relation] = []


class bitPattern:
    def __init__(self, bits, val):
        self.bits = bits
        self.val = val


class FrameInfo:
    def __init__(self, frame_id: int):
        self.id = frame_id
        self.dlc = 0
        self.isCycle = False
        self.BCAT = 0
        self.WCAT = 0
        self.signals: dict[str, Signal] = {}
        self.bit_pattern: dict[int, bitPattern] = {}


class CANMsg:
    def __init__(self, infos: list, flag):
        self.id = infos[0]
        self.dlc = infos[1]
        self.data = infos[2]
        self.timestamp = infos[3]
        self.signals: dict[str, float] = {}
        self.flag = flag


NORMAL = 0
ERROR = 1
ERROR_NOT_FOUND_ID = 2
ERROR_DLC = 3
ERROR_BIT_PATTERN = 4
ERROR_SIGNAL_INFO = 5
ERROR_SIGNAL_RELATION = 6
ERROR_INTERVAL = 7


FUZZY_ATTACK = 1
FABRICATION_ATTACK = 2
MASQUERADE_ATTACK = 3

