//
// Created by 17736 on 2024/5/19.
//

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "dbc_parse.h"
#include "utils.h"

// 定义一个结构来表示CAN信号
typedef struct {
    __uint32_t id;  // 使用ID代替name加快处理速度，ID = start_bit << 8 | length
    int start_bit;
    int length;
    int shift_bits;
    unsigned int mask;
} DBC_Signal;

// 定义一个结构来表示CAN消息
typedef struct {
    char name[32];
    int id;
    int dlc;
    int signal_count;
    DBC_Signal *signals;
} DBC_Message;

static HashTable *dbc_info;

static void extract_exception_signal(Message *msg) 
{
    Sig_Info *sig = msg->signals;
    msg->signal_count = msg->dlc;
    
    for(int i = 0; i < msg->dlc; i++) {
        sig[i].id = CAL_SIGNAL_ID(msg->id, i * 8 + 1, 8);
        sig[i].value = msg->data[i];
    }
}


static double extract_signal_value(__uint64_t data, const DBC_Signal* signal) 
{
    int shiftRight = 64 - signal->start_bit - signal->length + 1;
    unsigned int mask = (1 << signal->length) - 1;

    data >>= shiftRight;
    data &= mask;

    return data;
}

static void reverse_signal_info(DBC_Message *msg) 
{
    if (msg == NULL)
        return;
    int count = msg->signal_count;
    DBC_Signal *sigs = msg->signals;
    DBC_Signal temp;
    for (int i = 0; i < count / 2; i++) {
        memcpy(&temp, &sigs[count - i - 1], sizeof(DBC_Signal));
        memcpy(&sigs[count - i - 1], &sigs[i], sizeof(DBC_Signal));
        memcpy(&sigs[i], &temp, sizeof(DBC_Signal));
    }
}


void dbc_load_file(const char* dbc_file) 
{
    FILE *file = fopen(dbc_file, "r");
    if (!file) {
        perror("Failed to open file");
        exit(EXIT_FAILURE);
    }

    // 创建hash表
    dbc_info = hashTable_create();

    int count = 0;
    char line[128];
    DBC_Message *current_message = NULL;
    DBC_Signal *current_signal = NULL;

    while (fgets(line, sizeof(line), file)) {

        if (strncmp(line, "BO_", 3) == 0) {
            count++;
            reverse_signal_info(current_message);
            current_message = (DBC_Message*)malloc(sizeof(DBC_Message));
            DBC_Signal *signals = (DBC_Signal*) malloc(sizeof(DBC_Signal) * SIGNAL_INIT_SIZE);
            current_message->signals = signals;
            current_message->signal_count = 0;

            sscanf(line, "BO_ %d %s %d %*s",
                   &current_message->id, current_message->name, &current_message->dlc);
            
            hashTable_insert(dbc_info, current_message->id, current_message);
        }
        else if (strncmp(line, " SG_", 4) == 0 && current_message != NULL) {
            if (current_message->signal_count >= SIGNAL_INIT_SIZE)
                current_message->signals = (DBC_Signal*) realloc(current_message->signals, sizeof(DBC_Signal)*(current_message->signal_count + SIGNAL_ADD_SIZE));
            current_signal = &current_message->signals[current_message->signal_count];
            sscanf(line, " SG_ %*s : %d|%d@%*s", &current_signal->start_bit, &current_signal->length);
            current_signal->id = CAL_SIGNAL_ID(current_message->id, current_signal->start_bit, current_signal->length);
            current_signal->shift_bits = 64 - current_signal->start_bit - current_signal->length + 1;
            current_signal->mask = (1 << current_signal->length) - 1;
            current_message->signal_count ++;
        }
    }

    fclose(file);
    printf("Read DBC frame count: %d\n", count);
}


// 4E2003A0C63F8FFF
// Sig_0x20e_13_12: 34475276 2048
// Sig_0x20e_28_14: 34479118 396
// Sig_0x20e_46_10: 34483722 508
// Sig_0x20e_52_10: 34485258 511

Sig_Info *dbc_decode_msg(Message *msg)
{
    DBC_Message *dbc_message = (DBC_Message*)hashTable_search(dbc_info, msg->id);
    if (dbc_message) {
        // printf("Decoding CAN Message ID: %d\n", msg->id);
        Sig_Info *sig_info = msg->signals;

        int count = dbc_message->signal_count;

        msg->signal_count = count;
        __uint64_t payload = 0;

        for (int i = 0; i < msg->dlc; i++) 
            payload = payload << 8 | msg->data[i];
        
        __uint64_t data;
        for (int i = 0; i < count; i++) {
            const DBC_Signal *signal = &dbc_message->signals[i];

            data = payload >> signal->shift_bits;

            sig_info[i].value = data & signal->mask;
            sig_info[i].id = signal->id;
        }
        return sig_info;
    } else {
        extract_exception_signal(msg);
        return msg->signals;
    }
}


void dbc_destroy()
{
    HashNode *node, *prev;
    DBC_Message *tmp_msg;

    for (int i = 0; i < TABLE_SIZE; i++) {
        node = dbc_info->buckets[i];

        while (node != NULL) {  // release dbc message

            tmp_msg = (DBC_Message*)node->content;
            free(tmp_msg->signals);

            prev = node;
            node = node->next;
            free(prev->content);
            free(prev);
        }
    }
    free(dbc_info);
}

void dbc_display()
{
    HashNode *node;
    DBC_Message *tmp_msg;
    DBC_Signal *sig;
    for (int i = 0; i < TABLE_SIZE; i++) {
        node = dbc_info->buckets[i];

        while (node != NULL) {  // release dbc message
            tmp_msg = (DBC_Message*)node->content;
            
            printf("Msg ID: %d\tDLC: %d\tSignal Count: %d\n", tmp_msg->id, tmp_msg->dlc, tmp_msg->signal_count);
            sig = tmp_msg->signals;
            for (int j = 0; j < tmp_msg->signal_count; j++) {
                printf("\tSig ID: %d\tstart: %d\tlen: %d\n", sig->id, sig->start_bit, sig->length);
                sig++;
            }

            node = node->next;
        }
    }
}


// total 664 signals