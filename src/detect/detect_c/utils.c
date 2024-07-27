#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "utils.h"


__uint32_t hash(int key)
{
    return key % TABLE_SIZE;
}

HashTable *hashTable_create()
{
    HashTable *table = (HashTable *)malloc(sizeof(HashTable));
    for (int i = 0; i < TABLE_SIZE; i++) {
        table->buckets[i] = NULL;
    }
    return table;
}

Type hashTable_insert(HashTable *table, __uint32_t key, void *content)
{
    __uint32_t hash_index = hash(key);
    HashNode *new_node;

    if (hashTable_search(table, key))
        return False;

    new_node = (HashNode *)malloc(sizeof(HashNode));
    new_node->key = key;
    new_node->content = content;
    new_node->next = table->buckets[hash_index];
    table->buckets[hash_index] = new_node;

    return True;
}

void *hashTable_search(HashTable *table, __uint32_t key)
{
    if (table == NULL)
        return NULL;
    __uint32_t hash_index = hash(key);
    HashNode *node = table->buckets[hash_index];
    while (node != NULL) {
        if (node->key == key) {
            return node->content;
        }
        node = node->next;
    }
    return NULL;
}

void hashTable_delete(HashTable *table, __uint32_t key, void (*release)(void *content))
{
    __uint32_t hash_index = hash(key);
    HashNode *node = table->buckets[hash_index];
    HashNode *prev = NULL;
    while (node != NULL && node->key != key) {
        prev = node;
        node = node->next;
    }
    if (node == NULL)  // Key not found
        return;         
    if (prev == NULL) {
        table->buckets[hash_index] = node->next;
    }
    else {
        prev->next = node->next;
    }
    release(node->content);
    free(node);
}

void hashTable_destroy(HashTable *table, void (*release)(void *content))
{
    for (int i = 0; i < TABLE_SIZE; i++) {
        HashNode *node = table->buckets[i];
        while (node != NULL) {
            HashNode *temp = node;
            node = node->next;
            release(temp->content);
            free(temp);
        }
    }
    free(table);
}

void msg_release(void *content)
{
    Message *msg = (Message*)content;
    free(msg->signals);
    free(msg);
}

void msg_copy(Message **dest, Message *src)
{   
    *dest = (Message*)malloc(sizeof(Message));
    
    (*dest)->id = src->id;
    (*dest)->timestamp = src->timestamp;
    (*dest)->signal_count = src->signal_count;

    int size = sizeof(Sig_Info) * src->signal_count;
    (*dest)->signals = (Sig_Info*)malloc(size);
    memcpy((*dest)->signals, src->signals, size);

    // for (int i = 0; i < src->signal_count; i++) {
    //     (*dest)->signals[i].id = src->signals[i].id;
    //     (*dest)->signals[i].value = src->signals[i].value;
    // }
}

void null_release(void *content)
{
    return;
}

