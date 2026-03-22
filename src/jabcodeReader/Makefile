PREFIX 	=
CC 	= $(PREFIX)gcc
CFLAGS	 = -O2 -std=c11
LIBDIR	= ../jabcode/lib
LIBFLAGS = -L../jabcode/build -ljabcode -L$(LIBDIR) -ltiff -lpng16 -lz -lm

TARGET = bin/jabcodeReader

OBJECTS = $(patsubst %.c,%.o,$(wildcard *.c))

$(TARGET): $(OBJECTS)
	$(CC) $^ $(LIBFLAGS) $(CFLAGS) -o $@

$(OBJECTS): %.o: %.c
	$(CC) -c -I. -I../jabcode -I../jabcode/include $(CFLAGS) $< -o $@

clean:
	rm -f $(TARGET) $(OBJECTS)
