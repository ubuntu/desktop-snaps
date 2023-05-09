CC := gcc
CFLAGS := -O2
LDFLAGS := -fPIC -shared -Wl,-soname test
SRCS := $(shell find -name 'lib*.c')
OUTPUT := $(patsubst ./lib%.c,libtest.so.1.%,$(SRCS))

.PHONY: all clean

all: ${OUTPUT}

libtest.so.1.%: lib%.c
	${CC} $< ${CFLAGS} ${LDFLAGS} -o $@
	strip $@

clean:
	rm -f libtest.so.1.*
