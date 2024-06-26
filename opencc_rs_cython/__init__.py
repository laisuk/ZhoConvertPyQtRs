from .opencc_fmmseg_capi_wrapper import OpenCC as _OpenCC

CONFIG_LIST = [
    "s2t", "t2s", "s2tw", "tw2s", "s2twp", "tw2sp", "s2hk", "hk2s", "t2tw", "tw2t", "t2twp", "tw2t", "tw2tp",
    "t2hk", "hk2t", "t2jp", "jp2t"
]


class OpenCC(_OpenCC):
    def __init__(self, config="s2t"):
        self.config = config if config in CONFIG_LIST else "s2t"

    def zho_check(self, input_text):
        return super().zho_check(input_text)

    def convert(self, input_text, punctuation=False):
        return super().convert(input_text, punctuation)
