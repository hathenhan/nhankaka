"""CLI: python -m toshiko_crm <command>"""

import argparse
import json
import os
import sys

from .client import CRMError, ToshikoCRM


def _load_dotenv(path=".env"):
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                value = value[1:-1]
            os.environ.setdefault(key.strip(), value)


def main(argv=None):
    p = argparse.ArgumentParser(prog="toshiko_crm", description="Toshiko CRM API")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("login", help="Kiểm tra đăng nhập")

    d = sub.add_parser("order", help="Chi tiết đơn hàng")
    d.add_argument("order_id", type=int)

    a = sub.add_parser("assign-sale", help="Gán sale xử lý đơn hàng")
    a.add_argument("order_id", type=int)
    a.add_argument("sale_id", type=int)

    c = sub.add_parser("create-order", help="Tạo đơn hàng")
    c.add_argument("--phone", required=True)
    c.add_argument("--name", required=True)
    c.add_argument("--address", default="")
    c.add_argument("--source", default="")

    args = p.parse_args(argv)
    _load_dotenv()
    crm = ToshikoCRM()

    try:
        if args.cmd == "login":
            crm.login()
            result = {"ok": True, "message": "Đăng nhập thành công"}
        elif args.cmd == "order":
            result = crm.get_order(args.order_id)
        elif args.cmd == "assign-sale":
            result = crm.assign_sale(args.order_id, args.sale_id)
        else:
            result = crm.create_order(args.phone, args.name, args.address, args.source)
    except CRMError as e:
        print(f"Lỗi: {e}", file=sys.stderr)
        if e.payload is not None:
            print(json.dumps(e.payload, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
