from CANClass import CANMsg, FrameInfo, Relation
from rdflib import Namespace, Graph, BNode, Literal
from rdflib.namespace import RDF, RDFS
from bitarray import bitarray
import cantools
from cantools.database.can.signal import Signal

signals_0xFFF = [Signal('1', 0, 8), Signal('2', 8, 8),
                 Signal('3', 16, 8), Signal('4', 24, 8),
                 Signal('5', 32, 8), Signal('6', 40, 8),
                 Signal('7', 48, 8), Signal('8', 56, 8),
                 ]


# management knowledge graph
class KnowledgeGraph:
    def __init__(self):
        self.dbc_info = cantools.db.load_file(r'../data/DBC/anonymized.dbc')
        self._ivno = Namespace('http://localhost:8080/In-vehicleNetworkOntology#')
        self._map_frame_by_id: dict[int, Literal] = {}
        self._functions = []
        self._graph = Graph()
        self._graph.bind('ivno', self._ivno)
        self._signal_info: dict[str, Literal] = {}
        self._relation_info: list[str] = []

    def _add_a_frame(self, frame: FrameInfo):
        ivno = self._ivno
        g = self._graph

        f_id = frame.ID
        fra_kg = Literal('Fra_' + hex(f_id))
        g.add((fra_kg, RDF.type, ivno.Frame))
        g.add((fra_kg, ivno.hasID, Literal(f_id)))
        self._map_frame_by_id[f_id] = fra_kg
        for node, _, _ in g.triples((None, RDF.type, ivno.Function)):
            if node.value == frame.name:
                g.add((fra_kg, ivno.belongToFunction, node))
                break
        dlc = Literal(frame.dlc)  # Dlc
        g.add((fra_kg, ivno.hasDlc, dlc))
        if frame.isCycle:   # periodicity
            g.add((fra_kg, ivno.isCycle, Literal(True)))
            interval = Literal('Int_' + hex(f_id))
            g.add((fra_kg, ivno.hasInterval, interval))
            g.add((interval, ivno.BCSC, Literal(frame.jitter[0])))
            g.add((interval, ivno.WCSC, Literal(frame.jitter[1])))
        else:
            g.add((fra_kg, ivno.isCycle, Literal(False)))
        for key, item in frame.fix_bits.items():  # bits pattern
            tmp_bits = int.from_bytes(item[0], byteorder='little', signed=False)
            if tmp_bits == 0:
                continue
            ind, val = Literal(key), Literal(item[1])
            info = Literal('Bit_' + hex(f_id) + '_' + str(key + 1))
            bits = Literal(tmp_bits)
            g.add((fra_kg, ivno.hasFixBits, info))
            g.add((info, ivno.ind, ind))
            g.add((info, ivno.bits, bits))
            g.add((info, ivno.value, val))
        # signal info
        change_rate = frame.change_rate
        if f_id == 4095:
            node_signals = signals_0xFFF
        else:
            node_signals = self.dbc_info.get_message_by_frame_id(f_id).signals
        for key, item in frame.value_range.items():  # value range
            signal_node = None
            for ns in node_signals:
                if ns.name == key:
                    signal_node = ns
                    break
            signal_flag = hex(f_id) + '_' + str(signal_node.start) + '|' + str(signal_node.length)

            signal = Literal('Sig_' + signal_flag)
            self._signal_info['Sig_' + hex(f_id) + '_' + key] = signal

            g.add((fra_kg, ivno.hasSignal, signal))
            g.add((signal, RDF.type, self._ivno.Signal))

            name = Literal('Sig_' + signal_flag)
            g.add((signal, ivno.hasSignalName, name))
            scope = Literal('Ran_' + signal_flag)  # hasRange
            g.add((signal, ivno.hasRange, scope))
            g.add((scope, ivno.RangeMin, Literal(item[0])))
            g.add((scope, ivno.RangeMax, Literal(item[1])))
            rate = Literal(change_rate[key])   # change rate
            g.add((signal, ivno.hasRate, rate))

    def save_graph_as_turtle(self, destination):
        self._graph.serialize(destination=destination)

    def add_new_info(self, new_functions, new_frames):
        for fun in new_functions:
            if fun not in self._functions:
                self._functions.append(fun)
                fun_kg = Literal(fun)
                self._graph.add((fun_kg, RDF.type, self._ivno.Function))

        for frame in new_frames:
            Id = frame.ID  # id
            if Id in self._map_frame_by_id.keys():
                fra_kg = self._map_frame_by_id[Id]
                self._update_frame_info(fra_kg, frame)
            else:
                self._add_a_frame(frame)

        for frame in new_frames:
            self._add_relation(frame)

    def _add_relation(self, frame):
        ivno = self._ivno
        g = self._graph
        relation = frame.relation
        f_id = frame.ID

        signal_flag = hex(f_id) + '_'
        for rel in relation:
            start_signal = self._signal_info['Sig_' + signal_flag + rel.sourceAtt]
            end_signal = self._signal_info['Sig_' + hex(rel.endID) + '_' + rel.endAtt]
            end_frame = self._map_frame_by_id[rel.endID]
            rel_name = 'Rel_' + start_signal.value[4:] + '_' + end_signal.value[4:]
            if rel_name in self._relation_info:
                continue

            self._relation_info.append(rel_name)

            r = Literal(rel_name)
            g.add((start_signal, ivno.hasRelation, r))
            g.add((r, RDF.type, self._ivno.Relation))
            g.add((r, ivno.relateSignal, end_signal))
            g.add((r, ivno.relateFrame, end_frame))
            g.add((r, ivno.Correlation, Literal(rel.relationType)))

    def _update_frame_info(self, fra_kg: Literal, frame: FrameInfo):
        # update dlc
        node_dlc = self._graph.value(fra_kg, self._ivno.hasDlc)
        if node_dlc.value != frame.dlc:
            self._graph.set((fra_kg, self._ivno.hasDlc, Literal(frame.dlc)))

        # update fix values
        fix_bit = frame.fix_bits
        for _, _, node in self._graph.triples((fra_kg, self._ivno.hasFixBits, None)):
            ind = self._graph.value(node, self._ivno.ind).value
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
                        self._graph.remove((fra_kg, self._ivno.hasFixBits, node))
                        continue
                    new_val = g_val & tmp_val
                    new_val_l = Literal(int.from_bytes(new_val, byteorder='little', signed=False))
                    new_bits_l = Literal(int.from_bytes(new_bits, byteorder='little', signed=False))
                    self._graph.set((node, self._ivno.bits, new_bits_l))
                    self._graph.set((node, self._ivno.value, new_val_l))
            except KeyError:
                continue

        # update signal
        signal_range = frame.value_range
        change_rate = frame.change_rate
        if frame.ID == 4095:
            node_signals = signals_0xFFF
        else:
            node_signals = self.dbc_info.get_message_by_frame_id(frame.ID).signals
        for _, _, signal in self._graph.triples((fra_kg, self._ivno.hasSignal, None)):
            tmp = self._graph.value(signal, self._ivno.hasSignalName).value
            for node_signal in node_signals:
                str_tmp = str(node_signal.start) + '|' + str(node_signal.length)
                if str_tmp == tmp.split('_')[-1]:
                    signalName = node_signal.name
                    break
            try:
                if type(signal_range[signalName][0]) != int and type(signal_range[signalName][0]) != float:
                    continue
            except KeyError:
                print(frame.ID)
                print(frame.change_rate)
                continue
            # update value range
            newMin, newMax = signal_range[signalName]
            range_info = self._graph.value(signal, self._ivno.hasRange)
            maxVal = self._graph.value(range_info, self._ivno.RangeMax).value
            minVal = self._graph.value(range_info, self._ivno.RangeMin).value
            if newMin < minVal:
                self._graph.set((range_info, self._ivno.RangeMin, Literal(newMin)))
            if newMax > maxVal:
                self._graph.set((range_info, self._ivno.RangeMax, Literal(newMax)))
            # update value change rate
            max_rate = self._graph.value(signal, self._ivno.hasRate).value
            newRate = change_rate[signalName]
            if newRate > max_rate:
                self._graph.set((signal, self._ivno.hasRate, Literal(newRate)))


        # update time interval
        if self._graph.value(fra_kg, self._ivno.isCycle).value \
                and frame.isCycle:
            newMin = frame.jitter[0]
            newMax = frame.jitter[1]
            interval = self._graph.value(fra_kg, self._ivno.hasInterval)
            maxTs = self._graph.value(interval, self._ivno.WCSC).value
            minTs = self._graph.value(interval, self._ivno.BCSC).value
            if newMin < minTs:
                self._graph.set((interval, self._ivno.BCSC, Literal(newMin)))
            if newMax > maxTs:
                self._graph.set((interval, self._ivno.WCSC, Literal(newMax)))
        return True

