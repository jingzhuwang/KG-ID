//
// Created by 17736 on 2024/5/19.
//

#ifndef KG_ID_UTILS_H
#define KG_ID_UTILS_H

#define TABLE_SIZE 50

#define MSG_SIGNAL_MAX_SIZE 22

#define CAL_SIGNAL_ID(fid, start, len) ((fid) << 16 | (start) << 8 | (len))

typedef enum{ True=1, False=0} Type;

#pragma  pack(8)

typedef struct HashNode {
    __uint32_t key;
    void *content;
    struct HashNode *next;
} HashNode;

typedef struct {
    HashNode *buckets[TABLE_SIZE];
} HashTable;

typedef struct{
    __uint32_t id;
    float value;
} Sig_Info;

typedef struct {
    int id;
    int dlc;
    int signal_count;
    double timestamp;
    Sig_Info *signals;
    __uint32_t data[8];
} Message;


__uint32_t hash(int key);
HashTable *hashTable_create();
Type hashTable_insert(HashTable *table, __uint32_t key, void *content);
void *hashTable_search(HashTable *table, __uint32_t key);
void hashTable_delete(HashTable *table, __uint32_t key, void (*release)(void *content));
void hashTable_destroy(HashTable *table, void (*release)(void *content));

void msg_release(void *content);
void null_release(void *content);
void msg_copy(Message **dest, Message *src);


#endif //KG_ID_UTILS_H
