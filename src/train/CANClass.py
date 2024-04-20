import copy
from typing import Union
import numpy as np
from bitarray import bitarray


class Signal:
    def __init__(self, name, start, length):
        self.name = name
        self.start = start
        self.length = length


class CANMsg:
    def __init__(self, content, flag=True):
        self._id: int = content[0]
        self._len: int = int(content[1])
        self._data: bytes = copy.deepcopy(content[2])
        self._timestamp: float = content[3]
        self._normal: bool = flag

    @property
    def ID(self) -> int:
        return self._id

    @property
    def data(self) -> bytes:
        return self._data

    @property
    def time(self) -> float:
        return self._timestamp

    @property
    def len(self) -> int:
        return self._len

    @property
    def normal(self) -> bool:
        return self._normal

    def __format__(self, format_spec):
        string = 'ID: ' + str(hex(self._id)) + '\n'
        string += 'Len: ' + str(self._len) + '\n'
        string += 'Data: ' + self._data.hex() + '\n'
        string += 'Timestamp: ' + str(self._timestamp) + '\n'

        return string


class FrameInfo:
    _MAX_POSSIBLE_VALUE_NUMBER = 10
    _MAX_VARIANCE = 0.01

    def __init__(self, frame_id: int, des: str):
        self._id: int = frame_id  # frame id
        self._description: str = des  # frame description
        self._dlc: int = 0  # data length
        self._value_range: dict[Union[str, int], list[Union[float, int]]] = {}  # signal value range:{signal:[min, max]}
        self._change_rate: dict[Union[str, int], Union[int, float]] = {}  # signal value change rate: {signal: rate}
        self._state_change: dict[str, list[list[str]]] = {}  # signal state change: {signal: [state]}, str type signal
        self._interval: float = 0  # time interval
        self._jitter: list[int] = []  # time jitter: [min, max]
        self._constant: bool = False  # weather value change
        self._cycle: bool = True  # cycle frame
        self._relation: set[Relation] = set()  # relationship to other frame

        self._fix_bits: dict[int, [bitarray, int]] = {}
        self._last_data: dict[int, bitarray] = {}
        self._apper_time: list[float] = []  # last coming time
        self._status: dict[str, list] = {}  # last status

    def add_relation(self, rel):
        self._relation.add(rel)

    def set_dlc(self, new):
        self._dlc = new

    def set_fix_bits(self, byte, bit, value):
        try:
            self._fix_bits[byte][0] = bit
            self._fix_bits[byte][1] = value
        except KeyError:
            return

    def del_fix_bits(self, byte):
        self._fix_bits.pop(byte)

    def set_signal_range(self, signal, ran):
        self._value_range[signal] = ran

    def set_signal_rate(self, signal, rate):
        self._change_rate[signal] = rate

    def set_jitter(self, jitter):
        self._jitter = jitter

    @property
    def ID(self) -> int:
        return self._id

    @property
    def name(self) -> str:
        return self._description

    @property
    def isConstant(self) -> bool:
        return self._constant

    @property
    def status(self) -> dict:
        return self._status

    @property
    def time_series(self) -> list:
        return self._apper_time

    @property
    def dlc(self) -> int:
        return self._dlc

    @property
    def value_range(self) -> dict:
        return self._value_range

    @property
    def change_rate(self) -> dict:
        return self._change_rate

    @property
    def state_change(self) -> dict:
        return self._state_change

    @property
    def interval(self) -> float:
        return self._interval

    @property
    def jitter(self) -> list:
        return self._jitter

    @property
    def relation(self) -> set:
        return self._relation

    @property
    def isCycle(self) -> bool:
        return self._cycle

    @property
    def fix_bits(self) -> dict:
        return self._fix_bits

    def rel_clear(self):
        self._relation.clear()

    def cal_fix_value(self, data):
        if self._last_data:  # examine fixed values
            for key, item in self._last_data.items():
                tmp = bitarray("{:0>8}".format(bin(data[key])[2:]))
                bits = ~(tmp ^ item)
                if key in self._fix_bits.keys():
                    self._fix_bits[key][0] &= bits
                else:
                    self._fix_bits[key] = [bits, 0]
                self._last_data[key] = tmp
        else:  # initial fixed value
            for i, num in enumerate(data):
                self._last_data[i] = bitarray("{:0>8}".format(bin(num)[2:]))

    def handle_new_message(self, msg: CANMsg, info: dict[str, Union[float, str]]):
        """When a new message come, record its length, examine value property"""
        data = msg.data
        self._dlc = msg.len
        self.cal_fix_value(data)

        if self._status:
            for key in info.keys():
                self._status[key].append(info[key])
        else:
            for key in info.keys():
                self._status[key] = [info[key]]

        self._apper_time.append(msg.time)

    def _calculate_attribute(self):
        for key, item in list(self._fix_bits.items()):
            tmp = self._last_data[key] & item[0]
            self._fix_bits[key][1] = int.from_bytes(tmp, byteorder='big', signed=False)
        for key, val in self._status.items():
            len_val = len(val)
            if type(val[0]) == int or type(val[0]) == float:  # signal value is a number
                max_val = round(max(val), 4)
                min_val = round(min(val), 4)
                self._value_range[key] = [min_val, max_val]
                rate = 0.0
                for i in range(1, len_val):
                    if val[i - 1] == max_val:
                        continue
                    tmp = abs(val[i] - val[i - 1])
                    if tmp > rate:
                        rate = tmp
                self._change_rate[key] = round(rate, 4)
            else:
                self._state_change[key] = [[val[0]]]
                for i in range(1, len_val):
                    last = val[i - 1]
                    now = val[i]
                    if last == now:
                        continue
                    flag = True
                    item = self._state_change[key]
                    for sta in item:
                        if sta[-1] == last:
                            sta.append(now)
                            flag = False
                    if flag:
                        item.append([last, now])

    def _three_sigma(self, dataset, n=3):
        mean = np.mean(dataset)
        sigma = np.std(dataset)
        new_dataset = []
        for data in dataset:
            if abs(data - mean) > n * sigma:
                continue
            new_dataset.append(data)
        return new_dataset

    def _calculate_interval(self):
        """Handle message interval"""
        interval: list = []
        for i in range(0, len(self._apper_time) - 1):
            inv = self._apper_time[i + 1] - self._apper_time[i]
            interval.append(inv)
        if len(interval) == 0:  # only apper once
            self._interval = 0
            self._jitter.append(0)
            self._jitter.append(0)
        else:
            interval = self._three_sigma(interval, 5)
            var = np.var(interval, ddof=1)
            if var < self._MAX_VARIANCE:
                self._interval = round(np.mean(interval), 6)
                self._jitter = [round(min(interval), 6), round(max(interval), 6)]
            else:
                self._cycle = False

    def handle_info(self):
        self._calculate_attribute()
        self._calculate_interval()

    def __str__(self):
        des = ""
        des += "id: %d\n" % self._id
        des += "Description: %s\n" % self._description
        des += "DLC: " + self._dlc.__str__() + '\n'
        des += "Constant: " + self._constant.__str__() + '\n'
        des += "Value range: " + self._value_range.__str__() + '\n'
        des += "Change rate: " + self._change_rate.__str__() + '\n'
        des += "State Change: " + self._state_change.__str__() + '\n'
        for rel in self._relation:
            des += "Relation: " + rel.__str__() + '\n'
        if self._cycle:
            des += "Interval: %f" % self._interval + '\n'
            des += "Jitter: " + self._jitter.__str__() + '\n\n'
        return des


class Relation:
    def __init__(self, source_att: str, end_id: int, end_att: str, sup: float):
        self._source_att = source_att
        self._end_id = end_id
        self._end_att = end_att
        self._sup = sup

    @property
    def sourceAtt(self) -> str:
        return self._source_att

    @property
    def endID(self) -> int:
        return self._end_id

    @property
    def endAtt(self) -> str:
        return self._end_att

    @property
    def sup(self):
        return self._sup

    @property
    def relationType(self) -> bool:
        return True if self._sup > 0 else False

    def getInfo(self) -> list:
        return [self._source_att, self._end_id, self._end_att]

    def __str__(self):
        s = "from att: " + self._source_att
        s += " to " + str(self._end_id) + ':' + self._end_att
        return s

    def __hash__(self):
        return hash(self._source_att + str(self._end_id) + str(self._end_att))

    def __eq__(self, other):
        att, e_id, e_att = other.getInfo()
        if self._source_att == att and self._end_id == e_id and self._end_att == e_att:
            return True
        else:
            return False

    def __lt__(self, other):
        return self._sup < other.sup
