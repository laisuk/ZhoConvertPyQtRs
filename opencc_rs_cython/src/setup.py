from setuptools import setup
from setuptools.extension import Extension
from Cython.Build import cythonize

# Load opencc_fmmseg_capi.dll.lib
extensions = [
    Extension("opencc_fmmseg_capi_wrapper",
              ["opencc_fmmseg_capi_wrapper.pyx"],
              libraries=["opencc_fmmseg_capi.dll"],
              include_dirs=["."],
              library_dirs=["."]
              ),
]

setup(
    name='opencc_fmmseg_capi_wrapper',
    ext_modules=cythonize(extensions),
    include_package_data=True,  # This line is important to include the DLL in the package
)
