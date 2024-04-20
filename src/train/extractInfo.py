import csv
import re
import json

from bitarray import bitarray

from CANClass import CANMsg, FrameInfo, Relation
from kg_management import KnowledgeGraph
import cantools
from scipy.stats import pearsonr


Frames: list[FrameInfo] = []
DBC_FILE = r'../../data/DBC/anonymized.dbc'
DBC_INFO = cantools.db.load_file(DBC_FILE)
KG_FILE = r'../data/KG/kg_0.9'
MIN_SUPPORT = 0.9
node_file = r'../../data/DBC/nodes.csv'


def read_file_generator(trainFile):
    with open(trainFile, 'r', encoding='utf-8') as file:
        pattern = r'^\((.*?)\) can0 (.*?)#(.*?)$'
        while True:
            line = file.readline()
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
                msg = CANMsg(content)
                yield msg
            else:
                return


def find_frame(frame_id: int):
    for frame in Frames:
        if frame.ID == frame_id:
            return frame
    try:  # not found
        name = DBC_INFO.get_message_by_frame_id(frame_id).name
    except KeyError:
        name = 'Common'
    frame = FrameInfo(frame_id, name)
    Frames.append(frame)
    return frame


def find_time_index(time_series: list, time: int, index: int):
    time_window = 1000
    for i in range(index, len(time_series)):
        if time_series[i] > time:
            if time_series[i] < time + time_window:
                return i
            else:
                return -1
    return -1


def common_process(msg):
    info = {}
    data = msg.data
    for i in range(0, msg.len):
        info['Unknown_' + str(i)] = data[i]
    return info


def extract_node():
    frames_info = {}
    with open(node_file, newline='') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            frames_info[row[0]] = [row[1], row[2]]
    return frames_info


# extract information from message
def extract_info(trainFile):
    can_data = read_file_generator(trainFile)
    total = 0
    for msg in can_data:
        frame_id = msg.ID
        data = msg.data
        frame = find_frame(frame_id)
        try:
            info = DBC_INFO.decode_message(frame_id, data)
            if len(info) == 0:
                info = common_process(msg)
        except KeyError:
            info = common_process(msg)
        try:
            frame.handle_new_message(msg, info)
        except ValueError:
            print("ValueError: %d" % frame_id)
            print(info)
        total += 1
    print("total: " + str(total))
    for frame in Frames:
        frame.handle_info()


def save_info():
    try:
        saveFile = open(r'../data/extractInfo.csv', 'w', encoding='utf-8')
        for frame in Frames:
            info = frame.__str__()
            saveFile.write(info)
        saveFile.close()
    except IOError:
        print("Can't open save file!")


def extract_relation():
    num_counts = 100
    cal_ids = dict()
    for fra in Frames:
        if not fra.isConstant:
            times = fra.time_series
            if len(times) > num_counts:
                cal_ids[fra.ID] = len(times)
    cal_ids = sorted(cal_ids.items(), key=lambda x: x[1], reverse=True)
    ids = [x[0] for x in cal_ids]
    for i in range(0, len(ids)):
        y = ids[i]
        y_frame = find_frame(y)
        y_status = dict()
        for key, val in y_frame.status.items():
            if type(val[0]) != int and type(val[0]) != float:
                continue
            y_status[str(y) + ':' + str(key)] = [round(x, 4) for x in val]
        y_time = y_frame.time_series
        y_str = str(y)
        for j in range(i + 1, len(ids)):
            x = ids[j]
            x_frame = find_frame(x)
            x_status = dict()
            for key, val in x_frame.status.items():
                if type(val[0]) != int and type(val[0]) != float:
                    continue
                x_status[str(x) + ':' + str(key)] = [round(x, 4) for x in val]
            x_time = x_frame.time_series
            y_index = 0
            tmp = dict()
            for x_index, time in enumerate(x_time):
                y_index = find_time_index(y_time, time, y_index)
                if y_index == -1:
                    continue
                for key, val in y_status.items():
                    if key in tmp.keys():
                        tmp[key].append(val[y_index])
                    else:
                        tmp[key] = [val[y_index]]
                for key, val in x_status.items():
                    if key in tmp.keys():
                        tmp[key].append(val[x_index])
                    else:
                        tmp[key] = [val[x_index]]
            if tmp:
                for key in list(tmp.keys()):
                    val = set(tmp[key])
                    if len(val) == 1:
                        del tmp[key]
                if len(tmp) <= 1:
                    continue
                keys = list(tmp.keys())
                for ind in range(0, len(keys) - 1):
                    cor, p = pearsonr(tmp[keys[ind]], tmp[keys[ind + 1]])
                    if 0 < cor < MIN_SUPPORT or -MIN_SUPPORT < cor < 0:
                        continue
                    source_id, source_att = keys[ind].split(':')
                    end_id, end_att = keys[ind + 1].split(':')
                    source_frame = find_frame(int(source_id))
                    rel = Relation(source_att, int(end_id), end_att, cor)
                    source_frame.add_relation(rel)


def update_frame_info(origin: list[FrameInfo], new: list[FrameInfo]):

    origin_dict, new_dict = {}, {}
    for frame in origin:
        origin_dict[frame.ID] = frame
    for frame in new:
        new_dict[frame.ID] = frame
    for f_id, frame in origin_dict.items():
        try:
            f_new = new_dict[frame.ID]
        except KeyError:
            continue
        if f_new.dlc != frame.dlc:
            frame.set_dlc(f_new.dlc)

        # update fix values
        f_bits = frame.fix_bits
        new_bits = f_new.fix_bits
        for byte, v in f_bits.items():
            bit, val = v
            try:
                new_bit, new_val = new_bits[byte]
                if bit == new_bit and val == new_val:
                    continue
                else:
                    val_bitarray = bitarray("{:0>8}".format(bin(val)[2:]))
                    new_val_bitarray = bitarray("{:0>8}".format(bin(new_val)[2:]))
                    tmp_bit = ~(val_bitarray ^ new_val_bitarray) & (bit & new_bit)
                    tmp_val = val_bitarray & new_val_bitarray
                    frame.set_fix_bits(byte, tmp_bit, int.from_bytes(tmp_val, byteorder='little', signed=False))
            except KeyError:  # 这一 byte 位模式在另一数据文件中未出现
                frame.del_fix_bits(byte)

        # update signal
        f_signal_range = frame.value_range
        f_change_rate = frame.change_rate
        n_ranges = f_new.value_range
        n_rates = f_new.change_rate

        for name, ran in f_signal_range.items():
            n_ran = n_ranges[name]
            n_rate = n_rates[name]
            min_ran, max_ran = ran
            if min_ran > n_ran[0]:
                min_ran = n_ran[0]
            if max_ran < n_ran[1]:
                max_ran = n_ran[1]
            frame.set_signal_range(name, [min_ran, max_ran])
            if f_change_rate[name] < n_rate:
                frame.set_signal_rate(name, n_rate)

        f_relations = frame.relation
        n_relations = f_new.relation
        for rel in n_relations:
            for r in f_relations:
                if rel.sourceAtt != r.sourceAtt:
                    continue
                if rel.endAtt != r.endAtt or rel.endID != rel.endID:
                    frame.add_relation(rel)
                    break
        if f_new.isCycle and frame.isCycle:
            new_min, new_max = f_new.jitter
            f_min, f_max = frame.jitter
            if f_min > new_min:
                f_min = new_min
            if f_max < new_max:
                f_max = new_max
            frame.set_jitter([f_min, f_max])


def main():
    global KG_FILE, MIN_SUPPORT, Frames
    arg = 6
    KG_FILE = r'../../data/KG/KG-ID.ttl'
    MIN_SUPPORT += int(arg) / 100
    MIN_SUPPORT = round(MIN_SUPPORT, 2)
    graph = KnowledgeGraph()

    print('MIN_SUPPORT: ' + str(MIN_SUPPORT))
    print('KG_FILE: ' + str(KG_FILE))

    frame_to_node = extract_node()

    with open(r'../../data/ambient/capture_metadata.json') as f:
        f_json = json.load(f)
    frame_info = []
    for key, item in f_json.items():
        Frames = []
        train_file = r'../../data/ambient/' + key + '.log'
        print('*************START************')
        print(train_file)
        extract_info(train_file)
        extract_relation()
        if len(frame_info) == 0:
            frame_info = Frames
        else:
            update_frame_info(frame_info, Frames)
        print('*************END************')

    graph.add_new_info(frame_to_node, frame_info)
    graph.save_graph_as_turtle(KG_FILE)


if __name__ == '__main__':
    main()
