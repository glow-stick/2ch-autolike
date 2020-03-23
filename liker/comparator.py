#!/usr/bin/env python
# -*- coding: utf-8 -*- 

import wasmer

class Comparator:
    def __init__(self, bytecode, images):
        buffer_ptr = 102400 # 100K
        buffer_size = 409600 # 400K
        self.instance = wasmer.Instance(bytecode)
        self.memory = self.instance.memory.uint8_view()
        self.instance.exports.set_ptrs(buffer_ptr, buffer_ptr + buffer_size)
        self.buffer_ptr = self.instance.exports.get_buffer_ptr()
        self.db_ptr = self.instance.exports.get_db_ptr()
        self.memory_ptr = self.instance.exports.get_memory_ptr()
        for image in images:
            db_write_ptr = self.instance.exports.get_db_write_ptr()
            self.memory[db_write_ptr:db_write_ptr+len(image)] = image
            self.instance.exports.on_write_to_db(len(image))
        print(str(len(images)) + " images loaded")

    def compare(self, image, width, height):
        self.memory[self.buffer_ptr:self.buffer_ptr+len(image)] = image
        rate = self.instance.exports.find_buffer_in_db(width, height)
        return rate != -1 and rate < 10
