import ctypes
from rdflib import Graph, RDF, RDFS, Namespace
from type import *


class WorkingMemory:
    def __init__(self, knowledge_graph: Graph, prefix: Namespace):
        self.prefix = prefix
        self.frame_info: dict[int, FrameInfo] = {}
        self.signal_relation: dict[str, bool] = {}
        self.last_appear_time: dict[int, float] = {}
        self.last_signal_value: dict[int, dict[str, float]] = {}
        self.graph = knowledge_graph
        self.map_id_graph = {}
        for fra_kg, _, _ in self.graph.triples((None, RDF.type, prefix.Frame)):
            f_id = self.graph.value(fra_kg, prefix.ID).value
            self.map_id_graph[f_id] = fra_kg


class Rule_Match:
    def __init__(self):
        self._name = 'rule_match'

    def match(self, working_memory: WorkingMemory, msg: CANMsg):
        ivno = working_memory.prefix
        graph = working_memory.graph

        msg_id, msg_len = msg.id, msg.dlc
        msg_data, msg_ts = msg.data, msg.timestamp
        info = msg.signals

        if msg_id not in working_memory.map_id_graph.keys():
            return ERROR_NOT_FOUND_ID
        fra_kg = working_memory.map_id_graph[msg_id]

        dlc = graph.value(fra_kg, ivno.dlc).value
        if dlc != msg_len:
            return ERROR_DLC

        for _, _, node in graph.triples((fra_kg, ivno.bitPattern, None)):
            byte = graph.value(node, ivno.byte).value
            val = graph.value(node, ivno.value).value
            bits = graph.value(node, ivno.bits).value
            data = msg_data[byte]
            tmp = ctypes.c_uint8(bits & data)
            if tmp.value != val:
                return ERROR_BIT_PATTERN

        for _, _, signal in graph.triples((fra_kg, ivno.hasSignal, None)):
            signalName = graph.value(signal, ivno.name).value
            range_info = graph.value(signal, ivno.range)
            maxVal = graph.value(range_info, ivno.maxVal).value
            minVal = graph.value(range_info, ivno.minVal).value
            max_rate = graph.value(signal, ivno.rate).value

            now_val = round(info[signalName], 4)
            if now_val < minVal or now_val > maxVal:
                return ERROR_SIGNAL_INFO

            if msg_id not in working_memory.last_signal_value.keys():
                working_memory.last_signal_value[msg_id] = info
                return NORMAL

            last_status = working_memory.last_signal_value[msg_id]
            working_memory.last_signal_value[msg_id] = info
            rate = info[signalName] - last_status[signalName]
            if maxVal:
                max_possible = (last_status[signalName] + max_rate) % maxVal
                min_possible = (last_status[signalName] - max_rate + maxVal) % maxVal
            else:
                max_possible = last_status[signalName] + max_rate
                min_possible = last_status[signalName] - max_rate
            # change rate over normal rate
            if abs(rate) > max_rate and max_possible < info[signalName] < min_possible:
                return ERROR_SIGNAL_INFO

            if signalName in working_memory.signal_relation.keys():
                cor = working_memory.signal_relation[signalName]
                working_memory.signal_relation.pop(signalName)
                if rate < 0 and cor:  # signal decrease but relation is up
                    return ERROR_SIGNAL_RELATION
                elif rate > 0 and not cor:
                    return ERROR_SIGNAL_RELATION

            for _, _, rel in graph.triples((signal, ivno.hasRelation, None)):
                endSignale = graph.value(rel, ivno.relateSignal).value
                cor = graph.value(rel, ivno.type).value
                if (cor and rate > 0) or (not cor and rate < 0):  # 正相关
                    working_memory.signal_relation[endSignale] = True
                else:
                    working_memory.signal_relation[endSignale] = False

        # examine time interval
        if msg_id not in working_memory.last_appear_time.keys():
            working_memory.last_appear_time[msg_id] = msg_ts
            return NORMAL
        try:
            if graph.value(fra_kg, ivno.cycle).value:
                interval = graph.value(fra_kg, ivno.interval)
                wcat = graph.value(interval, ivno.WCAT).value
                bcat = graph.value(interval, ivno.BCAT).value
                last_ts = working_memory.last_appear_time[msg_id]
                maxTs = wcat + last_ts
                minTs = bcat + last_ts
                working_memory.last_appear_time[msg_id] = msg_ts
                if msg_ts < minTs or maxTs < msg_ts:
                    return ERROR_INTERVAL
        except AttributeError:
            return NORMAL
        return NORMAL


class InferenceEngine:
    def __init__(self, knowledge_graph: Graph, prefix: Namespace):
        self._working_memory = WorkingMemory(knowledge_graph, prefix)
        self._rules = []
        self._rules.append(Rule_Match())

    def inference(self, msg: CANMsg):
        ans = NORMAL
        for rule in self._rules:
            ans = rule.match(self._working_memory, msg)

        if ans == NORMAL:
            return NORMAL

        if ans == ERROR_NOT_FOUND_ID:
            return FUZZY_ATTACK
        elif ans == ERROR_BIT_PATTERN:
            return FABRICATION_ATTACK
        elif ans == ERROR_SIGNAL_RELATION:
            return MASQUERADE_ATTACK
