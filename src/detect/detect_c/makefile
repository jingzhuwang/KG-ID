# 指定编译器
CC = gcc
# CC = x86_64-linux-gnu-gcc

# 包含路径和库路径
CFLAGS = -g -I. -I/usr/local/include -I/usr/include/librdf -I/usr/include/raptor2 -I/usr/include/rasqal # 根据实际安装路径调整
LDFLAGS = -L/usr/local/lib -lrdf -lraptor2 -lrasqal

# 可执行文件
TARGET = my_program

# 源文件
SRCS = main.c read_kg.c utils.c dbc_parse.c # b.c e.c

# 目标文件
OBJS = $(SRCS:.c=.o)

# 生成可执行文件
$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) $(OBJS) $(LDFLAGS) -o $(TARGET)

# 编译每个源文件
%.o: %.c read_kg.h utils.h dbc_parse.h # d.h e.h
	$(CC) -c $(CFLAGS) $< -o $@

# 清理生成的文件
clean:
	rm -f $(OBJS) $(TARGET)

# 伪目标，防止与文件同名
.PHONY: clean
