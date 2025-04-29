import argparse

from dictionary_lib import DictionaryMaxlength

BLUE = "\033[1;34m"
RESET = "\033[0m"


def main():
    parser = argparse.ArgumentParser(
        description=f"{BLUE}Dict Generator: Command Line Dictionary Generator{RESET}"
    )
    parser.add_argument(
        "-f", "--format",
        choices=["zstd", "cbor", "json"],
        default="zstd",
        help="Dictionary format: [zstd|cbor|json]"
    )
    parser.add_argument(
        "-o", "--output",
        # dest="filename",
        help="Write generated dictionary to <OUTPUT> filename. If not specified, a default filename is used."
    )

    args = parser.parse_args()

    default_output = {
        "zstd": "dictionary_maxlength.zstd",
        "cbor": "dictionary_maxlength.cbor",
        "json": "dictionary_maxlength.json"
    }[args.format]

    output_file = args.output or default_output
    dictionaries = DictionaryMaxlength.from_dicts()

    if args.format == "zstd":
        dictionaries.save_compressed(output_file)
        print(f"{BLUE}Dictionary saved in ZSTD format at: {output_file}{RESET}")
    elif args.format == "cbor":
        dictionaries.serialize_to_cbor(output_file)
        print(f"{BLUE}Dictionary saved in CBOR format at: {output_file}{RESET}")
    elif args.format == "json":
        dictionaries.serialize_to_json(output_file)
        print(f"{BLUE}Dictionary saved in JSON format at: {output_file}{RESET}")


if __name__ == "__main__":
    main()
