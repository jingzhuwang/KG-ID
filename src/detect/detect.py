import ctypes
import os
import re
from rdflib import Graph, Namespace, RDF
from type import *
import cantools

ivno = Namespace('http://www.semanticweb.org/17736/ontologies/2024/2/ivno#')
DBC_FILE = r'../../data/DBC/anonymized_new.dbc'

graph_info: dict[int, FrameInfo] = {}
last_appear_time: dict[int, float] = {}
last_signal_value: dict[int, dict[str, float]] = {}
signal_relation: dict[str, bool] = {}

DBC_INFO = cantools.db.load_file(DBC_FILE)
graph = None

alpha = 0.05


def read_file_generator(filename):
    with open(filename, 'r', encoding='utf-8') as open_file:
        pattern = r'^\((.*?)\) can0 (.*?)#(.*?) (\d)$'
        while True:
            line = open_file.readline()
            if line:
                matchObj = re.match(pattern, line)
                content = [0, 8, 0, 0]
                if matchObj:
                    tmp = list(matchObj.groups())
                else:
                    continue
                content[0] = int(tmp[1], 16)  # id
                content[2] = bytes.fromhex(tmp[2])  # data
                content[3] = float(tmp[0])  # timestamp
                flag = True if int(tmp[3]) == 0 else False
                msg = Msg(content, flag)
                yield msg
            else:
                return


def read_graph():
    for fra_kg, _, _ in graph.triples((None, RDF.type, ivno.Frame)):
        f_id = graph.value(fra_kg, ivno.hasID).value
        frame = FrameInfo(f_id)
        graph_info[f_id] = frame

        node_dlc = graph.value(fra_kg, ivno.hasDlc)
        frame.dlc = node_dlc.value

        for _, _, node in graph.triples((fra_kg, ivno.hasFixBits, None)):
            ind = graph.value(node, ivno.byte).value
            val = graph.value(node, ivno.value).value
            bits = graph.value(node, ivno.bits).value
            tmp = bitPattern(bits, val)
            frame.bit_pattern[ind] = tmp

        for _, _, signal in graph.triples((fra_kg, ivno.hasSignal, None)):
            signalName = graph.value(signal, ivno.hasSignalName).value

            range_info = graph.value(signal, ivno.hasRange)
            maxVal = graph.value(range_info, ivno.maxVal).value
            minVal = graph.value(range_info, ivno.minVal).value
            max_rate = graph.value(signal, ivno.hasRate).value
            tmp = Signal(maxVal, minVal, max_rate)

            relations = []
            for _, _, rel in graph.triples((signal, ivno.hasRelation, None)):
                endFrame = graph.value(rel, ivno.relatedFrame).value
                endSignale = graph.value(rel, ivno.relatedSignal).value
                pos = graph.value(rel, ivno.Correlation).value
                r = Relation(endFrame, endSignale, pos)
                relations.append(r)
            tmp.rel = relations
            frame.signals[signalName] = tmp
        try:
            if graph.value(fra_kg, ivno.cycle).value:
                interval = graph.value(fra_kg, ivno.interval)
                frame.isCycle = True
                frame.period = graph.value(interval, ivno.period).value
                jitter = graph.value(interval, ivno.jitter)
                frame.jitter_min = graph.value(jitter, ivno.jitterMin).value
                frame.jitter_max = graph.value(jitter, ivno.jitterMax).value
        except AttributeError:
            frame.isCycle = False


def decode_message(msg):
    try:
        info = DBC_INFO.decode_message(msg.id, msg.data)
    except KeyError:
        info = {}
        data = msg.data
        sig_pre = 'Sig_' + hex(msg.id) + '_'
        for ind in range(0, msg.dlc):
            sig_name = sig_pre + str(ind * 8 + 1) + '_8'
            info[sig_name] = data[ind]
    return info


def match_feature(msg: Msg):
    msg_id, msg_len = msg.id, msg.dlc
    msg_data, msg_ts = msg.data, msg.timestamp
    info = msg.signals

    try:
        frame = graph_info[msg_id]
    except KeyError:
        return ERROR_NOT_FOUND_ID  # predict as attack

        # examine dlc
    dlc = frame.dlc
    if dlc != msg_len:
        return ERROR_DLC

    # examine fix values
    for byte, item in frame.bit_pattern.items():
        data = ctypes.c_uint8(msg_data[byte])
        tmp = ctypes.c_uint8(item.bits & data.value)
        if tmp.value != item.val:
            return ERROR_BIT_PATTERN

    # examine signal
    for signalName, signal in frame.signals.items():
        now_val = round(info[signalName], 4)
        maxVal = signal.maxVal
        minVal = signal.minVal
        if now_val < minVal or now_val > maxVal:
            return ERROR_SIGNAL_INFO

        # examine value change rate
        if msg_id not in last_signal_value.keys():
            last_signal_value[msg_id] = info
            return NORMAL
        last_status = last_signal_value[msg_id]
        last_signal_value[msg_id] = info
        rate = info[signalName] - last_status[signalName]
        max_rate = signal.rate
        if signal.maxVal:
            max_possible = (last_status[signalName] + max_rate) % maxVal
            min_possible = (last_status[signalName] - max_rate + maxVal) % maxVal
        else:
            max_possible = last_status[signalName] + max_rate
            min_possible = last_status[signalName] - max_rate
        # change rate over normal rate
        if abs(rate) > max_rate and max_possible < info[signalName] < min_possible:
            return ERROR_SIGNAL_INFO

        if signalName in signal_relation.keys():
            cor = signal_relation[signalName]
            signal_relation.pop(signalName)
            if rate < 0 and cor:  # signal decrease but relation is up
                return ERROR_SIGNAL_RELATION
            elif rate > 0 and not cor:
                return ERROR_SIGNAL_RELATION

        # relation cal
        for r in signal.rel:
            endSignale = r.targetSignal
            cor = r.type
            if (cor and rate > 0) or (not cor and rate < 0):  # 正相关
                signal_relation[endSignale] = True
            else:
                signal_relation[endSignale] = False

    # examine time interval
    if msg_id not in last_appear_time.keys():
        last_appear_time[msg_id] = msg_ts
        return NORMAL
    if frame.isCycle:
        last_ts = last_appear_time[msg_id]
        maxTs = last_ts + frame.period + frame.period * alpha + frame.jitter_max
        minTs = last_ts + frame.period - frame.period * alpha + frame.jitter_min
        last_appear_time[msg_id] = msg_ts
        if msg_ts < minTs or maxTs < msg_ts:
            return ERROR_INTERVAL
    return NORMAL


def detect(fileName):
    test_data = read_file_generator(fileName)
    for msg in test_data:
        msg.signals = decode_message(msg)
        res = match_feature(msg)
        if res != NORMAL:
            print("Attack")


if __name__ == '__main__':
    graph = Graph()
    graph.bind('ivno', ivno)
    kg_f = r'../../data/KG/KG-ID_avg_period.ttl'
    graph.parse(kg_f, format='turtle')
    read_graph()
    
    path = r'../../data/attacks_with_label/'
    files = os.listdir(path)
    print(files)
    print('*************START************')
    for name in files:
        file = path + name
        print(file)
        detect(file)
        print('------------------------------------------')
    print('*************EDN************')
