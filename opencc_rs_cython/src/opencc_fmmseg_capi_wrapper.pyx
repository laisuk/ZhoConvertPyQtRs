# opencc_fmmseg_capi_wrapper.pyx

cdef extern from "opencc_fmmseg_capi.h":
    void *opencc_new()
    char *opencc_convert(const void *instance, const char *input_text, const char *config, bint punctuation)
    bint opencc_get_parallel(const void *instance)
    void opencc_set_parallel(const void *instance, bint is_parallel)
    int opencc_zho_check(const void *instance, const char *input_text)
    void opencc_free(const void *instance)
    void opencc_string_free(const char *ptr)
    char *opencc_last_error()

CONFIG_LIST = [
    b"s2t", b"t2s", b"s2tw", b"tw2s", b"s2twp", b"tw2sp", b"s2hk", b"hk2s",
    b"t2tw", b"tw2t", b"t2twp", b"tw2t", b"tw2tp", b"t2hk", b"hk2t", b"t2jp", b"jp2t"
]

cdef class OpenCC:
    cdef void *ptr
    cdef bytes _config
    OpenCC(bytes)

    def __cinit__(self, config=b"s2t"):
        self.ptr = opencc_new()
        self.config = config

    property config:
        def __get__(self):
            return self._config
        def __set__(self, value):
            if isinstance(value, str):
                value = value.encode('utf-8')
            if value not in CONFIG_LIST:
                value = b's2t'
            self._config = value

    def __dealloc__(self):
        if self.ptr:
            opencc_free(self.ptr)
            self.ptr = NULL  # Set pointer to NULL after freeing memory

    def convert(self, input_text, punctuation=True):
        input_bytes = input_text.encode('utf-8')
        config_bytes = self.config
        cdef char *result = opencc_convert(self.ptr, input_bytes, config_bytes, punctuation)
        try:
            if result is not NULL:
                return result.decode('utf-8')
            else:
                return ""
        finally:
            if result is not NULL:
                opencc_string_free(result)

    def get_parallel(self):
        return opencc_get_parallel(self.ptr)

    def set_parallel(self, is_parallel):
        opencc_set_parallel(self.ptr, is_parallel)

    def zho_check(self, input_text):
        input_bytes = input_text.encode('utf-8')
        return opencc_zho_check(self.ptr, input_bytes)

    def last_error(self):
        return opencc_last_error().decode('utf-8')
