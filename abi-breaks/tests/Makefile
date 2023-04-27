all: libtest.so.1.1 libtest.so.1.2 libtest.so.1.3
	strip libtest.so.1.*

CCPARAMS=-fPIC -shared -Wl,-soname test

libtest.so.1.1: lib1.c
	gcc lib1.c ${CCPARAMS} -o libtest.so.1.1
libtest.so.1.2: lib2.c
	gcc lib2.c ${CCPARAMS} -o libtest.so.1.2
libtest.so.1.3: lib3.c
	gcc lib3.c ${CCPARAMS} -o libtest.so.1.3

clean:
	rm -f libtest.so.1.*
