# KG-ID: Knowledge Graph-Based Intrusion Detection on In-Vehicle Network

This repository provides a knowledge graph-based intrusion detection (KG-ID) implementation for the CAN bus. KG-ID consists of three modules: 1) knowledge extraction module that utilizes data mining methods to extract the CAN frame and signal features from different types of data; 2) knowledge graph construction module that uses the established ontology model to store knowledge in the form of graph; and 3) attack detection module which detects the message on the CAN bus by leveraging the DBC and knowledge graph. The modules in KG-ID are as follows:

**CANClass.py**: contains data structure used in training and detection

**kg_construction.py**: constructs the knowledge graph

**extractionInfo.py**: extracts features and relations from CAN traffic

**detect.py**: detect CAN messages

**KG-ID.ttl**: knowledge graph saved as turtle format

The folder detect_c provides detection code implemented in C language.
