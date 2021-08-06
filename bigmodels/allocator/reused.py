from typing import List
from .base import Allocator
import cupy

class ReusedAllocator(Allocator):
    def __init__(self, size, temp_size):
        total = size + temp_size

        self.__base_ptr = cupy.cuda.Memory(total)
        self.__allocate_limit = size
        self.__offset = 0

    def reset(self):
        self.__offset = 0
    
    def _alloc(self, size):

        offset = self.__offset
        self.__offset += size
        if self.__offset > self.__allocate_limit:
            raise RuntimeError("Memory limit exceeded %d > %d" % (self.__offset, self.__allocate_limit))
        return cupy.cuda.MemoryPointer(self.__base_ptr, offset)
    
    @property
    def temp_ptr(self):
        return cupy.cuda.MemoryPointer(self.__base_ptr, self.__allocate_limit)