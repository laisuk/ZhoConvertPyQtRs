import io
import sys
from opencc_py import OpenCC

def main(args):
    if args.config is None:
        print("Please specify conversion.", file=sys.stderr)
        return 1

    opencc = OpenCC(args.config)

    with io.open(args.input if args.input else 0, encoding=args.in_enc) as f:
        input_str = f.read()
    output_str = opencc.convert(input_str, args.punct)

    with io.open(args.output if args.output else 1, 'w', encoding=args.out_enc) as f:
        f.write(output_str)

    in_from = args.input if args.input else "<stdin>"
    out_to = args.output if args.output else "stdout"
    print(f"Conversion completed ({args.config}): {in_from} -> {out_to}", file=sys.stderr)

    return 0
