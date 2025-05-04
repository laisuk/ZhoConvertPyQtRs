from __future__ import print_function

import argparse
import sys
from . import dict_generate
from . import convert_cmd  # We'll move your current logic into convert_cmd.py

def main():
    parser = argparse.ArgumentParser(
        prog='opencc_py',
        description='OpenCC CLI with multiple tools',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', required=True)

    # ---- convert subcommand ----
    parser_convert = subparsers.add_parser('convert', help='Convert text using OpenCC')
    parser_convert.add_argument('-i', '--input', metavar='<file>', help='Input file')
    parser_convert.add_argument('-o', '--output', metavar='<file>', help='Output file')
    parser_convert.add_argument('-c', '--config', metavar='<conversion>', help='Conversion configuration')
    parser_convert.add_argument('-p', '--punct', metavar='<boolean>', default=False, help='Punctuation conversion: True/False')
    parser_convert.add_argument('--in-enc', metavar='<encoding>', default='UTF-8', help='Input encoding')
    parser_convert.add_argument('--out-enc', metavar='<encoding>', default='UTF-8', help='Output encoding')
    parser_convert.set_defaults(func=convert_cmd.main)

    # ---- dict-generate subcommand ----
    parser_dict = subparsers.add_parser('dict-generate', help='Generate dictionary')
    parser_dict.add_argument(
        "-f", "--format",
        choices=["zstd", "cbor", "json"],
        default="zstd",
        help="Dictionary format: [zstd|cbor|json]"
    )
    parser_dict.add_argument(
        "-o", "--output",
        metavar="<filename>",
        help="Write generated dictionary to <filename>. If not specified, a default filename is used."
    )
    parser_dict.set_defaults(func=dict_generate.main)

    args = parser.parse_args()
    return args.func(args)

if __name__ == '__main__':
    sys.exit(main())
