import cantools
from bitarray import bitarray
from rdflib import Namespace, Graph, Literal, URIRef
from rdflib.namespace import RDF

from CANClass import FrameInfo, Signal

signal_4095 = [Signal(name='Unknown_0', start=1, length=8),
               Signal(name='Unknown_1', start=9, length=8),
               Signal(name='Unknown_2', start=17, length=8),
               Signal(name='Unknown_3', start=25, length=8),
               Signal(name='Unknown_4', start=33, length=8),
               Signal(name='Unknown_5', start=41, length=8),
               Signal(name='Unknown_6', start=49, length=8),
               Signal(name='Unknown_7', start=57, length=8)]


class KnowledgeGraph:
    def __init__(self):
        self.dbc_info = cantools.db.load_file(r'../../data/DBC/anonymized.dbc')
        self._ivno = Namespace('http://www.semanticweb.org/17736/ontologies/2024/2/ivno#')
        self._map_frame_by_id: dict[int, URIRef] = {}
        self._module_info: dict[str, URIRef] = {}
        self._node_info: dict[str, URIRef] = {}
        self._graph = Graph()
        self._graph.bind('ivno', self._ivno)

    def _add_a_frame(self, frame: FrameInfo):
        ivno = self._ivno
        g = self._graph

        f_id = frame.ID
        fra_kg = URIRef('Fra_' + hex(f_id))
        g.add((fra_kg, RDF.type, ivno.Frame))
        g.add((fra_kg, ivno.ID, Literal(f_id)))
        self._map_frame_by_id[f_id] = fra_kg

        dlc = Literal(frame.dlc)  # Dlc
        g.add((fra_kg, ivno.dlc, dlc))
        if frame.isCycle:
            g.add((fra_kg, ivno.cycle, Literal(True)))
            interval = URIRef('Cyc_' + hex(f_id))
            g.add((fra_kg, ivno.interval, interval))
            g.add((interval, ivno.BCAT, Literal(frame.jitter[0])))
            g.add((interval, ivno.WCAT, Literal(frame.jitter[1])))
        else:
            g.add((fra_kg, ivno.isCycle, Literal(False)))
        for key, item in frame.fix_bits.items():  # fixValue
            tmp_bits = int.from_bytes(item[0], byteorder='little', signed=False)
            if tmp_bits == 0:
                continue
            ind, val = Literal(key), Literal(item[1])
            info = URIRef('Bit_' + hex(f_id) + '_' + str(key + 1))
            bits = Literal(tmp_bits)
            g.add((fra_kg, ivno.bitPattern, info))
            g.add((info, ivno.byte, ind))
            g.add((info, ivno.bits, bits))
            g.add((info, ivno.value, val))
        # hasSignal----------number type
        change_rate = frame.change_rate
        relation = frame.relation
        try:
            node_signals = self.dbc_info.get_message_by_frame_id(f_id).signals
        except KeyError:
            node_signals = signal_4095
        for key, item in frame.value_range.items():  # value range
            signal_node = None
            for ns in node_signals:
                if ns.name == key:
                    signal_node = ns
                    break
            signal_flag = hex(f_id) + '_' + str(signal_node.start) + '_' + str(signal_node.length)

            signal = URIRef('Sig_' + signal_flag)
            g.add((fra_kg, ivno.hasSignal, signal))
            name = Literal('Sig_' + signal_flag)
            g.add((signal, ivno.name, name))
            scope = URIRef('Ran_' + signal_flag)  # hasRange
            g.add((signal, ivno.range, scope))
            g.add((scope, ivno.minVal, Literal(item[0])))
            g.add((scope, ivno.maxVal, Literal(item[1])))
            rate = Literal(change_rate[key])
            g.add((signal, ivno.rate, rate))
            rel_set = self._find_relation(relation, key)
            for rel in rel_set:
                r = URIRef(ivno + 'Rel_' + signal_flag)
                g.add((signal, ivno.hasRelation, r))
                g.add((r, ivno.relateFrame, Literal(rel.endID)))
                g.add((r, ivno.relateSignal, Literal(rel.endAtt)))
                g.add((r, ivno.type, Literal(rel.relationType)))
        return fra_kg

    def save_graph_as_turtle(self, destination):
        self._graph.serialize(destination=destination)

    def read_from_turtle(self, filename):
        self._graph.parse(filename, format='turtle')
        for frame, _, _ in self._graph.triples((None, RDF.type, self._ivno.Frame)):
            f_id = self._graph.value(frame, self._ivno.ID).value
            self._map_frame_by_id[f_id] = frame

    def add_new_info(self, frame_to_node, new_frames):
        for frame in new_frames:
            Id = frame.ID  # id
            if Id in self._map_frame_by_id.keys():
                fra_kg = self._map_frame_by_id[Id]
                self._update_frame_info(fra_kg, frame)
            else:
                fra_kg = self._add_a_frame(frame)
                node, module = frame_to_node[Id]
                if node not in self._node_info.keys():
                    node_kg = URIRef(self._ivno + node)
                    self._node_info[node] = node_kg
                else:
                    node_kg = self._node_info[node]
                self._graph.add((node_kg, RDF.type, self._ivno.Node))
                self._graph.add((node_kg, self._ivno.name, Literal(node)))
                self._graph.add((node_kg, self._ivno.send, fra_kg))
                self._graph.add((fra_kg, self._ivno.sentBy, node_kg))
                if module not in self._module_info.keys():
                    module_kg = URIRef(self._ivno + module)
                    self._module_info[module] = module_kg
                else:
                    module_kg = self._module_info[module]
                self._graph.add((module_kg, RDF.type, self._ivno.Module))
                self._graph.add((module_kg, self._ivno.name, Literal(module)))
                self._graph.add((module_kg, self._ivno.containNode, node_kg))

    def _update_frame_info(self, fra_kg: URIRef, frame: FrameInfo):
        # update dlc
        node_dlc = self._graph.value(fra_kg, self._ivno.dlc)
        if node_dlc.value != frame.dlc:
            self._graph.set((fra_kg, self._ivno.dlc, URIRef(self._ivno + str(frame.dlc))))

        # update fix values
        fix_bit = frame.fix_bits
        for _, _, node in self._graph.triples((fra_kg, self._ivno.bitPattern, None)):
            ind = self._graph.value(node, self._ivno.byte).value
            val = self._graph.value(node, self._ivno.value).value
            bits = self._graph.value(node, self._ivno.bits).value
            try:
                bit_info = fix_bit[ind]
                g_val = bitarray("{:0>8}".format(bin(val)[2:]))
                g_bits = bitarray("{:0>8}".format(bin(bits)[2:]))
                tmp_val = bitarray("{:0>8}".format(bin(bit_info[1])[2:]))
                tmp_bits = bit_info[0]
                if g_val == tmp_val and g_bits == tmp_bits:
                    continue
                else:
                    new_bits = ~(g_val ^ tmp_val) & (g_bits & tmp_bits)
                    if int.from_bytes(new_bits, byteorder='little', signed=False) == 0:
                        self._graph.remove((node, None, None))
                        self._graph.remove((fra_kg, self._ivno.bitPattern, node))
                        continue
                    new_val = g_val & tmp_val
                    new_val_l = URIRef(self._ivno + str(int.from_bytes(new_val, byteorder='little', signed=False)))
                    new_bits_l = URIRef(self._ivno + str(int.from_bytes(new_bits, byteorder='little', signed=False)))
                    self._graph.set((node, self._ivno.bits, new_bits_l))
                    self._graph.set((node, self._ivno.value, new_val_l))
            except KeyError:
                continue

        # update signal
        signal_range = frame.value_range
        change_rate = frame.change_rate
        relation = frame.relation
        node_signals = self.dbc_info.get_message_by_frame_id(frame.ID).signals
        for _, _, signal in self._graph.triples((fra_kg, self._ivno.hasSignal, None)):
            tmp = self._graph.value(signal, self._ivno.name).value
            for node_signal in node_signals:
                str_tmp = str(node_signal.start) + '_' + str(node_signal.length)
                if str_tmp == tmp.split('_')[-1]:
                    signalName = node_signal.name
            try:
                if type(signal_range[signalName][0]) != int and type(signal_range[signalName][0]) != float:
                    continue
            except KeyError:
                print(frame.ID)
                print(frame.change_rate)
                continue
            # update value range
            newMin, newMax = signal_range[signalName]
            range_info = self._graph.value(signal, self._ivno.range)
            maxVal = self._graph.value(range_info, self._ivno.maxVal).value
            minVal = self._graph.value(range_info, self._ivno.minVal).value
            if newMin < minVal:
                self._graph.set((range_info, self._ivno.minVal, Literal(newMin)))
            if newMax > maxVal:
                self._graph.set((range_info, self._ivno.maxVal, Literal(newMax)))
            # update value change rate
            max_rate = self._graph.value(signal, self._ivno.hasRate).value
            newRate = change_rate[signalName]
            if newRate > max_rate:
                self._graph.set((signal, self._ivno.rate, Literal(newRate)))
            # update relation
            for r in relation:
                if r.sourceAtt != signalName:
                    continue
                flag = False
                for _, _, rel in self._graph.triples((signal, self._ivno.hasRelation, None)):
                    endFrame = self._graph.value(rel, self._ivno.relateFrame).value
                    endSignale = self._graph.value(rel, self._ivno.relateSignal).value
                    if endSignale == r.endAtt and endFrame == r.endID:
                        flag = True
                        break
                if not flag:
                    rel = Literal('Rel' + tmp[3:])
                    self._graph.add((signal, self._ivno.hasRelation, rel))
                    self._graph.add((rel, self._ivno.relateFrame, Literal(r.endID)))
                    self._graph.add((rel, self._ivno.relateSignal, Literal(r.endAtt)))
                    self._graph.add((rel, self._ivno.type, Literal(r.relationType)))

        # update time interval
        if self._graph.value(fra_kg, self._ivno.cycle).value \
                and frame.isCycle:
            newMin = frame.jitter[0]
            newMax = frame.jitter[1]
            interval = self._graph.value(fra_kg, self._ivno.interval)
            maxTs = self._graph.value(interval, self._ivno.WCAT).value
            minTs = self._graph.value(interval, self._ivno.BCAT).value
            if newMin < minTs:
                self._graph.set((interval, self._ivno.BCAT, Literal(newMin)))
            if newMax > maxTs:
                self._graph.set((interval, self._ivno.WCAT, Literal(newMax)))
        return True

    def _find_relation(self, relations, key):
        ans = []
        for rel in relations:
            if rel.sourceAtt == key:
                ans.append(rel)
        return ans
