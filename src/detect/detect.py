import os
import re
import time
from rdflib import Graph, Namespace
from type import *
from inference_engine import InferenceEngine
import cantools

ivno = Namespace('http://www.semanticweb.org/17736/ontologies/2024/2/ivno#')
DBC_FILE = r'../../data/DBC/anonymized_new.dbc'

DBC_INFO = cantools.db.load_file(DBC_FILE)
graph = None


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
                msg = CANMsg(content, flag)
                yield msg
            else:
                return


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


def detect(infMachine: InferenceEngine, fileName):
    test_data = read_file_generator(fileName)
    for msg in test_data:
        msg.signals = decode_message(msg)
        res = infMachine.inference(msg)
        if res != NORMAL:
            print('Attack')


if __name__ == '__main__':
    graph = Graph()
    graph.bind('ivno', ivno)
    kg_f = r'../../data/KG/KG-ID.ttl'
    graph.parse(kg_f, format='turtle')

    infModel = InferenceEngine(graph, ivno)
    path = r'../../data/attacks_with_label/'
    files = os.listdir(path)
    print(files)
    for name in files:
        file = path + name
        print(file)
        detect(infModel, file)
        print('------------------------------------------')
