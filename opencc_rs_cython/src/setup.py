from setuptools import setup
from setuptools.extension import Extension
from Cython.Build import cythonize
import platform

# Load opencc_fmmseg_capi.dll.lib
system = platform.system()
extra_link_args = []
if system == "Linux":
    extra_link_args = ["-Wl,-rpath,$ORIGIN"]
elif system == "Darwin":
    extra_link_args = ["-Wl,-rpath,@loader_path"]

extensions = [
    Extension("opencc_fmmseg_capi_wrapper", ["opencc_fmmseg_capi_wrapper.pyx"],
              libraries=["opencc_fmmseg_capi"],
              include_dirs=["."],
              library_dirs=["."],
              extra_link_args=extra_link_args
              ),
]

setup(
    name='opencc_fmmseg_capi_wrapper',
    ext_modules=cythonize(extensions),
    include_package_data=True,  # This line is important to include the DLL in the package
)
