#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "read_kg.h"
#include "dbc_parse.h"
#include <time.h>

#define DEBUG 0
#define DISPLAY_INFO 0
// #define REAL_CAR_ENV


#ifdef REAL_CAR_ENV

static const char kg_file[] = {"kg.ttl"};
static const char dbc_file[] = {"database.dbc"};
static const char attack_file[] = {"fuzzing_attack.log"};
static const char log_file[] = {"ans.log"};

#else

static const char kg_file[] = {"../data/kg.ttl"};
static const char dbc_file[] = {"../data/database.dbc"};
static const char attack_file[] = {"../data/fuzzing_attack_1.log"};
static const char log_file[] = {"ans.log"};

#endif

static const char *msg_pattern = "(%lf) can0 %3s#%s 0";

static HashTable *pre_status;
static HashTable *rel_signals;

static Type *pos_flag;
static Type *neg_flag;
static Sig_Info *last_signal_status;


void initialize();
void release_resource();
void parse_line(const char *line, Message *msg);
Type detect_attack(Message *msg);


int main(int argc, char *argv[])
{
    char line[64];
    Message *msg = (Message*)malloc(sizeof(Message));
    msg->signals = (Sig_Info*)malloc(sizeof(Sig_Info) * MSG_SIGNAL_MAX_SIZE);
    msg->signal_count = 0;
    Type detect_ans;

    printf("Start program!\n");
    initialize();

    int err = 0;

    FILE *file = fopen(attack_file, "r");
    if (!file) {
        perror("Failed to open file");
        exit(EXIT_FAILURE);
    }
    FILE *logger = fopen(log_file, "a");
    if (!logger) {
        perror("Failed to open file");
        exit(EXIT_FAILURE);
    }
    int count = 49000;
    clock_t time_count = 0;
    while (count && fgets(line, sizeof(line), file)) {
        parse_line(line, msg);

#if DEBUG
        printf("ID: %d\n", msg->id);
        for (int i = 0; i < msg->dlc; i++)
            printf("%02X ", msg->data[i]);
#endif
        count--;
        clock_t start = clock();
        detect_ans = detect_attack(msg);
        clock_t end = clock();
        time_count = time_count + end - start;
        // printf("run time: %f per ms\n", ((double)(end - start)) / CLOCKS_PER_SEC);
        if (detect_ans == False)
            err++;
    }

    
    // printf("error number: %d\n", err);
    printf("time count: %ld\n", time_count);
    fprintf(logger, "run time origin: %ld\n", time_count);
    fprintf(logger, "run time: %f\n", (double)(time_count / CLOCKS_PER_SEC));

    fclose(file);
    fclose(logger);

    free(msg->signals);
    free(msg);
    release_resource();

    printf("end!\n");
    return 0;
}

void initialize()
{
    kg_read_ttl(kg_file);
    // printf("read_kg() success!\n");
    dbc_load_file(dbc_file);


#if DISPLAY_INFO
    kg_display();
    dbc_display();
#endif

    pre_status = hashTable_create();
    rel_signals = hashTable_create();

    last_signal_status = (Sig_Info*)malloc(sizeof(Sig_Info) * MSG_SIGNAL_MAX_SIZE);

    pos_flag = (Type*)malloc(sizeof(Type));
    neg_flag = (Type*)malloc(sizeof(Type));
    *pos_flag = True;
    *neg_flag = False;
}

void release_resource()
{

    kg_destroy();
    dbc_destroy();

    hashTable_destroy(pre_status, msg_release);
    hashTable_destroy(rel_signals, null_release);
    free(last_signal_status);
    free(pos_flag);
    free(neg_flag);
}

// 解码CAN数据文件行信息
void parse_line(const char *line, Message *msg)
{
    static char tmp_id[4];
    static char str_data[17];

    // (1000000000.000002) can0 522#DF7FD0007F08001C 0
    sscanf(line, msg_pattern, &msg->timestamp, tmp_id, str_data);

    msg->id = strtol(tmp_id, NULL, 16);
    msg->dlc = strlen(str_data) / 2;

    for (int i = 0; i < msg->dlc; i++) {
        sscanf(&str_data[i * 2], "%2x", &msg->data[i]);
    }
}


void copy_now_signal_value(Message *msg, Sig_Info *now)
{
    int size = msg->signal_count * sizeof(Sig_Info);

    Sig_Info* pre = msg->signals;

    memcpy(last_signal_status, pre, size);
    memcpy(pre, now, size);

    // for (int i = 0; i < count; i++) {
    //     last_signal_status[i].id = pre[i].id;
    //     last_signal_status[i].value = pre[i].value;
    //     pre[i].id = now[i].id;
    //     pre[i].value = now[i].value;
    // }
}

Type detect_attack(Message *msg)
{
    Frame *kg_frame = kg_search_frame(msg->id);   // search kg info
    if (kg_frame == NULL)
        return False;
    
    Sig_Info *sig_info = dbc_decode_msg(msg);   // decode message

    if (msg->dlc != kg_frame->dlc)  // examine dlc
        return False;
    
    unsigned int bits, val;
    Bit_pattern *bit_pattern = kg_frame->bit_pattern;
    for (int i = 0; i < msg->dlc; i++) {   // examine bit pattern
        bits = bit_pattern[i].bits;
        val = bit_pattern[i].value;
        if ((msg->data[i] & bits) != val)
            return False;
    }
    
    Message *prev_msg = (Message*)hashTable_search(pre_status, msg->id);
    if (prev_msg == NULL) {
        Message *tmp;
        msg_copy(&tmp, msg);
        hashTable_insert(pre_status, tmp->id, tmp);
        return True;
    }
    else {
        copy_now_signal_value(prev_msg, sig_info);
    }

    Type *rel_cor;
    float value, rate, max_pos, min_pos, last_val;
    Relation *rel;
    int index = 0;
    int signal_count = msg->signal_count;
    Signal *signal = kg_frame->signals;

    while (signal != NULL) {
        __uint32_t id = signal->id;
        double max = signal->range.max;
        double min = signal->range.min;
        double rate = signal->rate;

        for (; index < signal_count; index++) {
            if (id == sig_info[index].id)
                break;
        }
        if (index == signal_count)
            return False;
        value = sig_info[index].value;


        if (value < min || value > max)  // examine value range
            return False;

        last_val = last_signal_status[index].value;
        rate = value - last_val;

        if (max) {
            max_pos = (int)(last_val + rate) % (int)max;
            min_pos = (int)(last_val - rate + max) % (int)max;
        }
        else {
            max_pos = last_val + rate;
            min_pos = last_val - rate;
        }

        if (abs(rate) > rate && max_pos < value < min_pos)
            return False;

        rel_cor = (Type*)hashTable_search(rel_signals, id);
        if (rel_cor != NULL) {
            hashTable_delete(rel_signals, id, null_release);
            if (rate < 0 && *rel_cor)
                return False;
            else if (rate > 0 && *rel_cor == False)
                return False; 
        }

        rel = signal->rel;
        while (rel != NULL) {
            if ((rel->type && rate > 0) || (rel->type == False && rate < 0))   // 
                hashTable_insert(rel_signals, rel->tar_sig, pos_flag);
            else
                hashTable_insert(rel_signals, rel->tar_sig, neg_flag);
            rel = rel->next;
        }
        signal = signal->next;
    }

    if (kg_frame->cycle) {
        int max_ts = kg_frame->interval.max + prev_msg->timestamp;
        int min_ts = kg_frame->interval.min + prev_msg->timestamp;
        prev_msg->timestamp = msg->timestamp;
        if (max_ts < msg->timestamp || min_ts > msg->timestamp)
            return False;
    }
    return True;
}


// valgrind -s --leak-check=full ./my_program
