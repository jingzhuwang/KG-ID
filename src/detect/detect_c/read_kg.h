//
// Created by 17736 on 2024/5/19.
//

#ifndef KG_ID_READ_KG_H
#define KG_ID_READ_KG_H

#include "utils.h"

#pragma  pack(8)

typedef struct {
    double max;
    double min;
} Range;

#define Interval Range

typedef struct Relation{
    int tar_fra;
    __uint32_t tar_sig;
    Type type;
    struct Relation *next;
}Relation;

typedef struct Signal{
    __uint32_t id;
    Range range;
    double rate;
    Relation *rel;
    struct Signal *next;
} Signal;

typedef struct{
    __uint32_t bits;
    __uint32_t value;
}Bit_pattern;

typedef struct {
    int id;
    int dlc;
    Bit_pattern bit_pattern[8];
    Signal *signals;
    Type cycle;
    Interval interval;
} Frame;


Frame* kg_search_frame(int key);
void kg_read_ttl(const char *kg_file);
void kg_destroy();
void kg_display();
void kg_printf_frame_info(Frame *frame);

#endif //KG_ID_READ_KG_H
