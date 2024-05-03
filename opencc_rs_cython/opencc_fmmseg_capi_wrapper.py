import importlib.util
from pkg_resources import resource_filename


def __bootstrap__():
    __file__ = resource_filename(__name__, 'opencc_fmmseg_capi_wrapper.cp312-win_amd64.pyd')
    __loader__ = None
    del __bootstrap__, __loader__
    spec = importlib.util.spec_from_file_location(__name__, __file__)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)


__bootstrap__()
