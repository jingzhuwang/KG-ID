import re
import json

from CANClass import CANMsg, FrameInfo, Relation
from kg_management import KnowledgeGraph
import cantools
from scipy.stats import pearsonr


Frames: list[FrameInfo] = []
DBC_FILE = r'../data/DBC/anonymized.dbc'
DBC_INFO = cantools.db.load_file(DBC_FILE)
FUNCTION = set()
MIN_SUPPORT = 0.9


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
    # deal with 0xFFF
    info = {}
    data = msg.data
    for i in range(0, msg.len):
        info[str(i+1)] = data[i]
    return info


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
        FUNCTION.add(frame.name)


# extract relation between signals
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
                    source_frame.addRelation(rel)


def main():
    global MIN_SUPPORT, FUNCTION, Frames
    arg = 6
    KG_FILE = r'ivno_kg_base.ttl'
    MIN_SUPPORT += int(arg) / 100   # used in pearson coefficient
    MIN_SUPPORT = round(MIN_SUPPORT, 2)
    graph = KnowledgeGraph()

    print('MIN_SUPPORT: ' + str(MIN_SUPPORT))
    print('KG_FILE: ' + str(KG_FILE))

    with open(r'../data/ambient/capture_metadata.json') as f:
        f_json = json.load(f)

    for key, item in f_json.items():
        FUNCTION = set()
        Frames = []
        train_file = r'../data/ambient/' + key + '.log'
        print('*************START************')
        print(train_file)
        extract_info(train_file)
        extract_relation()
        graph.add_new_info(FUNCTION, Frames)
        print('*************END************')

    graph.save_graph_as_turtle(KG_FILE)


if __name__ == '__main__':
    main()
