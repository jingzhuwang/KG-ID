//
// Created by 17736 on 2024/5/19.
//
#include <stdio.h>
#include <stdlib.h>
#include <librdf.h>
#include <string.h>

#include "read_kg.h"
#include "utils.h"

// save knowledge graph
static HashTable *frames;

// prefix
static const char *ivno_str = "http://www.semanticweb.org/17736/ontologies/2024/2/ivno#";

librdf_world *world;
librdf_storage *storage;
librdf_model *model;
librdf_uri *uri;
librdf_uri *ivno;
librdf_node *node_type, *ivno_frame, *ivno_id, *ivno_dlc, *ivno_cycle, *ivno_bitPattern, *ivno_interval;
librdf_node *ivno_bcat, *ivno_wcat, *ivno_signal, *ivno_rel_frame, *ivno_rel_sig, *ivno_rel_type;
librdf_node *ivno_sig_name, *ivno_sig_range, *ivno_sig_ran_max, *ivno_sig_ran_min, *ivno_sig_rate, *ivno_rel;
librdf_node *ivno_bp_bits, *ivno_bp_byte, *ivno_bp_value;

static __uint32_t extract_signal_id(const char *str)
{
    int start, len, id;
    // 找到最后两个 '_' 符号的位置
    char value1[8], value2[8], value3[8];

    // 使用 sscanf 提取子字符串
    sscanf(str, "Sig_%[^_]_%[^_]_%[^_]", value1, value2, value3);

    id = strtol(value1, NULL, 16); // 将十六进制字符串转换为整型
    start = atoi(value2); // 将十进制字符串转换为整型
    len = atoi(value3);

    return CAL_SIGNAL_ID(id, start, len);
}

// startup the library
static void init_librdf(const char *kg_file)
{
    // Initialize Redland RDF library
    world = librdf_new_world();
    librdf_world_open(world);

    // Create storage and model
    storage = librdf_new_storage(world, "memory", NULL, NULL);
    model = librdf_new_model(world, storage, NULL);

    // Create parser
    librdf_parser *parser = librdf_new_parser(world, "turtle", NULL, NULL);

    // Parse file
    uri = librdf_new_uri_from_filename(world, kg_file);
    if (librdf_parser_parse_into_model(parser, uri, NULL, model)) {
        fprintf(stderr, "Failed to parse RDF file\n");
        return;
    }
    librdf_free_parser(parser);
    parser = NULL;

    ivno = librdf_new_uri(world, (const unsigned char *)ivno_str);
    node_type = librdf_new_node_from_uri_string(world, (const unsigned char *)"http://www.w3.org/1999/02/22-rdf-syntax-ns#type");
    ivno_frame = librdf_new_node_from_uri_local_name(world, ivno, "Frame");
    ivno_id = librdf_new_node_from_uri_local_name(world, ivno, "ID");
    ivno_dlc = librdf_new_node_from_uri_local_name(world, ivno, "dlc");
    ivno_cycle = librdf_new_node_from_uri_local_name(world, ivno, "cycle");
    ivno_bitPattern = librdf_new_node_from_uri_local_name(world, ivno, "bitPattern");
    ivno_interval = librdf_new_node_from_uri_local_name(world, ivno, "interval");
    ivno_bcat = librdf_new_node_from_uri_local_name(world, ivno, "BCAT");
    ivno_wcat = librdf_new_node_from_uri_local_name(world, ivno, "WCAT");
    ivno_signal = librdf_new_node_from_uri_local_name(world, ivno, "hasSignal");
    ivno_rel_frame = librdf_new_node_from_uri_local_name(world, ivno, "relateFrame");
    ivno_rel_sig = librdf_new_node_from_uri_local_name(world, ivno, "relateSignal");
    ivno_rel_type = librdf_new_node_from_uri_local_name(world, ivno, "type");
    ivno_sig_name = librdf_new_node_from_uri_local_name(world, ivno, "name");
    ivno_sig_range = librdf_new_node_from_uri_local_name(world, ivno, "range");
    ivno_sig_ran_max = librdf_new_node_from_uri_local_name(world, ivno, "maxVal");
    ivno_sig_ran_min = librdf_new_node_from_uri_local_name(world, ivno, "minVal");
    ivno_sig_rate = librdf_new_node_from_uri_local_name(world, ivno, "rate");
    ivno_rel = librdf_new_node_from_uri_local_name(world, ivno, "hasRelation");
    ivno_bp_bits = librdf_new_node_from_uri_local_name(world, ivno, "bits");
    ivno_bp_byte = librdf_new_node_from_uri_local_name(world, ivno, "byte");
    ivno_bp_value = librdf_new_node_from_uri_local_name(world, ivno, "value");
}

static void destroy_librdf()
{
    // Clean up
    librdf_free_uri(uri);
    librdf_free_uri(ivno);
    // librdf_free_node(node_type);   // 在read_ttl()->librdf_free_statement(state_frame);中以释放
    // librdf_free_node(ivno_frame);
    librdf_free_node(ivno_id);
    librdf_free_node(ivno_dlc);
    librdf_free_node(ivno_cycle);
    librdf_free_node(ivno_bitPattern);
    librdf_free_node(ivno_bp_bits);
    librdf_free_node(ivno_bp_byte);
    librdf_free_node(ivno_bp_value);
    librdf_free_node(ivno_interval);
    librdf_free_node(ivno_bcat);
    librdf_free_node(ivno_wcat);
    librdf_free_node(ivno_signal);
    librdf_free_node(ivno_sig_name);
    librdf_free_node(ivno_sig_range);
    librdf_free_node(ivno_sig_ran_max);
    librdf_free_node(ivno_sig_ran_min);
    librdf_free_node(ivno_sig_rate);
    librdf_free_node(ivno_rel);
    librdf_free_node(ivno_rel_frame);
    librdf_free_node(ivno_rel_sig);
    librdf_free_node(ivno_rel_type);

    librdf_free_model(model);
    librdf_free_storage(storage);
    librdf_free_world(world);
}

static double search_single_value(librdf_node *subject, librdf_node *predicate)
{
    librdf_node *sub = librdf_new_node_from_node(subject);
    librdf_node *pre = librdf_new_node_from_node(predicate);
    librdf_statement *state = librdf_new_statement_from_nodes(world, sub, pre, NULL);
    librdf_stream *stream = librdf_model_find_statements(model, state);
    double ans = 0;

    while (!librdf_stream_end(stream)) {
        librdf_statement *statement = librdf_stream_get_object(stream);
        librdf_node *object = librdf_statement_get_object(statement); // frame node

        char *object_str = (char *)librdf_node_get_literal_value(object);
        if (object_str[0] == 't')
            ans = 1;
        else if (object_str[0] == 'f')
            ans = 0;
        else
            ans = atof(object_str);

        // free(object_str);
        librdf_stream_next(stream);
    }

    librdf_free_stream(stream);
    librdf_free_statement(state);

    return ans;
}

static librdf_node *search_single_node(librdf_node *subject, librdf_node *predicate)
{
    librdf_node *sub = librdf_new_node_from_node(subject);
    librdf_node *pre = librdf_new_node_from_node(predicate);
    librdf_statement *state = librdf_new_statement_from_nodes(world, sub, pre, NULL);
    librdf_stream *stream = librdf_model_find_statements(model, state);

    librdf_node *ans = NULL;
    while (!librdf_stream_end(stream)) {
        librdf_statement *statement = librdf_stream_get_object(stream);
        ans = librdf_statement_get_object(statement); // frame node

        librdf_stream_next(stream);
    }

    librdf_free_stream(stream);
    librdf_free_statement(state);

    return ans;
}

static Relation *search_relation(librdf_node *subject, librdf_node *predicate)
{
    Relation *relations = NULL;

    librdf_node *sub = librdf_new_node_from_node(subject);
    librdf_node *pre = librdf_new_node_from_node(predicate);
    librdf_statement *state = librdf_new_statement_from_nodes(world, sub, pre, NULL);
    librdf_stream *stream = librdf_model_find_statements(model, state);

    librdf_node *tmp;

    while (!librdf_stream_end(stream)) {
        librdf_statement *statement = librdf_stream_get_object(stream);
        librdf_node *object = librdf_statement_get_object(statement); // relation node

        Relation *relation = (Relation *)malloc(sizeof(Relation));

        relation->tar_fra = search_single_value(object, ivno_rel_frame); // relate frame

        tmp = search_single_node(object, ivno_rel_sig); // relate signal
        char *tmp_str = (char *)librdf_node_get_literal_value(tmp);
        relation->tar_sig = extract_signal_id(tmp_str);
        // free(tmp_str);

        relation->type = (Type)search_single_value(object, ivno_rel_type);

        relation->next = relations;

        relations = relation;

        librdf_stream_next(stream);
    }
    librdf_free_stream(stream);
    librdf_free_statement(state);

    return relations;
}

static Signal *search_signal(librdf_node *subject, librdf_node *predicate)
{
    Signal *signals = NULL;

    librdf_node *sub = librdf_new_node_from_node(subject);
    librdf_node *pre = librdf_new_node_from_node(predicate);
    librdf_statement *state = librdf_new_statement_from_nodes(world, sub, pre, NULL);
    librdf_stream *stream = librdf_model_find_statements(model, state);

    librdf_node *tmp;

    while (!librdf_stream_end(stream)) {
        librdf_statement *statement = librdf_stream_get_object(stream);
        librdf_node *object = librdf_statement_get_object(statement); // signal node

        Signal *signal = (Signal *)malloc(sizeof(Signal));

        tmp = search_single_node(object, ivno_sig_name); // signal name
        char *tmp_str = (char *)librdf_node_get_literal_value(tmp);
        signal->id = extract_signal_id(tmp_str);
        // free(tmp_str);

        tmp = search_single_node(object, ivno_sig_range); // signal range
        signal->range.max = search_single_value(tmp, ivno_sig_ran_max);
        signal->range.min = search_single_value(tmp, ivno_sig_ran_min);

        signal->rate = search_single_value(object, ivno_sig_rate); // signal rate

        signal->rel = search_relation(object, ivno_rel);

        signal->next = signals;

        signals = signal;

        librdf_stream_next(stream);
    }
    librdf_free_stream(stream);
    librdf_free_statement(state);

    return signals;
}

static void search_bit_pattern(librdf_node *subject, librdf_node *predicate, Bit_pattern *patterns)
{
    librdf_node *sub = librdf_new_node_from_node(subject);
    librdf_node *pre = librdf_new_node_from_node(predicate);
    librdf_statement *state = librdf_new_statement_from_nodes(world, sub, pre, NULL);
    librdf_stream *stream = librdf_model_find_statements(model, state);

    librdf_node *tmp;
    int ind = 0;

    while (!librdf_stream_end(stream)) {
        librdf_statement *statement = librdf_stream_get_object(stream);
        librdf_node *object = librdf_statement_get_object(statement); // bit pattern node

        ind = search_single_value(object, ivno_bp_byte); // byte

        patterns[ind].bits = search_single_value(object, ivno_bp_bits);
        patterns[ind].value = search_single_value(object, ivno_bp_value);

        librdf_stream_next(stream);
    }
    librdf_free_stream(stream);
    librdf_free_statement(state);
}

void kg_read_ttl(const char *kg_file)
{
    librdf_stream *stream;
    int count = 0;
    init_librdf(kg_file);

    frames = hashTable_create();

    librdf_node *tmp;
    // Print model contents
    librdf_statement *state_frame = librdf_new_statement_from_nodes(world, NULL, node_type, ivno_frame);
    stream = librdf_model_find_statements(model, state_frame);
    
    Frame *frame;
    while (!librdf_stream_end(stream)) { // frame
        count++;
        librdf_statement *statement = librdf_stream_get_object(stream);
        librdf_node *frame_node = librdf_statement_get_subject(statement); // frame node
        
        frame = (Frame *)malloc(sizeof(Frame));
        memset(frame, 0, sizeof(Frame));

        // frame_node->usage ++;
        frame->dlc = (int)search_single_value(frame_node, ivno_dlc); // dlc

        frame->id = (int)search_single_value(frame_node, ivno_id); // id

        frame->signals = search_signal(frame_node, ivno_signal);

        search_bit_pattern(frame_node, ivno_bitPattern, frame->bit_pattern);

        frame->cycle = (Type)search_single_value(frame_node, ivno_cycle);
        if (frame->cycle)
        {
            tmp = search_single_node(frame_node, ivno_interval);
            frame->interval.max = search_single_value(tmp, ivno_wcat);
            frame->interval.min = search_single_value(tmp, ivno_bcat);
        }
        hashTable_insert(frames, frame->id, (void*)frame);

        librdf_stream_next(stream);
    }

    librdf_free_stream(stream);

    librdf_free_statement(state_frame);

    destroy_librdf();
    printf("Read knowledge graph frame count %d\n", count);

    return;
}

Frame *kg_search_frame(int key)
{
    void *ptr = hashTable_search(frames, key);
    if (ptr)
        return (Frame *)ptr;
    else 
        return NULL;
}

void kg_destroy()
{
    HashNode *node, *prev;
    Frame *tmp_frame;
    Signal *tmp_signal, *prev_signal;
    Relation *tmp_rel, *prev_rel;

    for (int i = 0; i < TABLE_SIZE; i++) {
        node = frames->buckets[i];
        while (node != NULL) {  // release frame

            tmp_frame = (Frame *)node->content;
            tmp_signal = tmp_frame->signals;

            while (tmp_signal != NULL) {  // release signal
                tmp_rel = tmp_signal->rel;

                while (tmp_rel != NULL) { // release relation
                    prev_rel = tmp_rel;
                    tmp_rel = tmp_rel->next;
                    free(prev_rel);
                }

                prev_signal = tmp_signal;
                tmp_signal = tmp_signal->next;
                free(prev_signal);
            }

            prev = node;
            node = node->next;
            free(prev->content);
            free(prev);
        }
    }
    free(frames);
}

void kg_display()
{
    HashNode *node;
    Frame *tmp_frame;
    int count = 0;
    for (int i = 0; i < TABLE_SIZE; i++) {
        node = frames->buckets[i];
        while (node != NULL) { 
            tmp_frame = (Frame *)node->content;    //  frame
            kg_printf_frame_info(tmp_frame);
            count ++;
            node = node->next;
        }
    }
    printf("total: %d\n", count);
}

void kg_printf_frame_info(Frame *frame)
{
    printf("id: %d\tdlc: %d\n", frame->id, frame->dlc);
    printf("bit pattern: \n");

    for (int i = 0; i < 8; i++)
        printf("byte: %d\tbits: %d\tvalue: %d\n", i, frame->bit_pattern[i].bits, frame->bit_pattern[i].value);

    Signal* signal = frame->signals;

    while (signal != NULL) { //  signal
        printf("signal id: %d\trate: %f\n", signal->id, signal->rate);
        printf("range max: %f\trange min: %f\n", signal->range.max, signal->range.min);

        Relation *rel = signal->rel;

        while (rel != NULL) { //  relation
            printf("rel tar frame: %d\trel tar sig: %d\ttype: %d\n", rel->tar_fra, rel->tar_sig, rel->type);
            rel = rel->next;
        }

        signal = signal->next;
    }

    printf("*****************************\n");
}

