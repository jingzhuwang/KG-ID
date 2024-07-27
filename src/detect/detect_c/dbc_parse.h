//
// Created by 17736 on 2024/5/19.
//

#ifndef KG_ID_DBC_PARSE_H
#define KG_ID_DBC_PARSE_H

#include "utils.h"


#define SIGNAL_INIT_SIZE 5
#define SIGNAL_ADD_SIZE 5

void dbc_load_file(const char* dbc_file);
Sig_Info *dbc_decode_msg(Message *msg);
void dbc_destroy();
void dbc_display();

#endif //KG_ID_DBC_PARSE_H
