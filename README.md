# Kết nối API Toshiko CRM

Client Python (không cần cài thư viện ngoài, Python 3.8+) cho API của `https://crm.toshiko.vn`.

## Cấu hình

```bash
cp .env.example .env   # rồi điền TOSHIKO_CRM_EMAIL và TOSHIKO_CRM_PASSWORD
```

Mật khẩu chỉ nằm trong `.env` (đã được `.gitignore`), không đưa vào mã nguồn.

## Dùng từ dòng lệnh

```bash
python -m toshiko_crm login
python -m toshiko_crm order 535155
python -m toshiko_crm assign-sale 535155 33
python -m toshiko_crm create-order --phone 0983609090 --name "Lê Đặng Nguyên" --address "Hà Nội" --source FB
```

## Dùng trong code

```python
from toshiko_crm import ToshikoCRM, CRMError

crm = ToshikoCRM()            # đọc email/mật khẩu từ biến môi trường
try:
    order = crm.create_order("0983609090", "Lê Đặng Nguyên", "Hà Nội", "FB")
    detail = crm.get_order(535155)
    crm.assign_sale(535155, 33)
except CRMError as e:
    print(e, e.status, e.payload)
finally:
    crm.logout()
```

Client tự đăng nhập ở lần gọi đầu, gắn header `Authorization: Bearer <token>`, và tự đăng nhập lại một lần nếu token hết hạn (HTTP 401).

## API

| Hàm | Method | Đường dẫn |
| --- | --- | --- |
| `login()` | POST | `/api/login` |
| `logout()` | GET | `/api/users/logout` |
| `get_order(order_id)` | GET | `/api/ords/detail/{order_id}` |
| `assign_sale(order_id, sale_id)` | PUT | `/api/ords/assign/{order_id}/sale` |
| `create_order(phone, name, address, source)` | POST | `/api/ords/create` |

## Test

```bash
python -m unittest discover -s tests -v
```
