"""Client for the Toshiko CRM API (https://crm.toshiko.vn).

Endpoints follow the "Hướng dẫn kết nối API CRM" sheet:

    POST /api/login                     -> access_token
    GET  /api/users/logout
    GET  /api/ords/detail/{order_id}
    PUT  /api/ords/assign/{order_id}/sale   body {"id": sale_id}
    POST /api/ords/create               body {PhoneNumber, CustomerName, Address, Source}

No third-party dependencies.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Callable, Optional

DEFAULT_BASE_URL = "https://crm.toshiko.vn"

# (method, url, headers, body_bytes, timeout) -> (http_status, response_text)
Transport = Callable[[str, str, dict, Optional[bytes], float], "tuple[int, str]"]


class CRMError(Exception):
    """The CRM rejected a request or answered with something unexpected."""

    def __init__(self, message: str, status: Optional[int] = None, payload: Any = None):
        super().__init__(message)
        self.status = status
        self.payload = payload


def _urllib_transport(method, url, headers, body, timeout):
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except urllib.error.URLError as e:
        raise CRMError(f"Không kết nối được tới CRM: {e.reason}") from e


class ToshikoCRM:
    def __init__(
        self,
        email: Optional[str] = None,
        password: Optional[str] = None,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        timeout: float = 30,
        transport: Transport = _urllib_transport,
    ):
        self.email = email or os.environ.get("TOSHIKO_CRM_EMAIL")
        self.password = password or os.environ.get("TOSHIKO_CRM_PASSWORD")
        self.base_url = (
            base_url or os.environ.get("TOSHIKO_CRM_BASE_URL") or DEFAULT_BASE_URL
        ).rstrip("/")
        self.token = token or os.environ.get("TOSHIKO_CRM_TOKEN")
        self.timeout = timeout
        self._transport = transport

    # ---- auth ---------------------------------------------------------

    def login(self) -> str:
        """Log in and store the bearer token. Returns the token."""
        if not self.email or not self.password:
            raise CRMError(
                "Thiếu thông tin đăng nhập: đặt TOSHIKO_CRM_EMAIL và TOSHIKO_CRM_PASSWORD."
            )
        data = self._request(
            "POST",
            "/api/login",
            {"email": self.email, "password": self.password},
            auth=False,
        )
        token = data.get("access_token") if isinstance(data, dict) else None
        if not token:
            raise CRMError("Đăng nhập không trả về access_token.", payload=data)
        self.token = token
        return token

    def logout(self) -> Any:
        if not self.token:
            return None
        try:
            return self._request("GET", "/api/users/logout", retry_auth=False)
        finally:
            self.token = None

    # ---- orders -------------------------------------------------------

    def get_order(self, order_id: int) -> Any:
        """2.1 Thông tin chi tiết đơn hàng."""
        return self._request("GET", f"/api/ords/detail/{int(order_id)}")

    def assign_sale(self, order_id: int, sale_id: int) -> Any:
        """2.2 Gán sale xử lý đơn hàng."""
        return self._request(
            "PUT", f"/api/ords/assign/{int(order_id)}/sale", {"id": int(sale_id)}
        )

    def create_order(
        self, phone_number: str, customer_name: str, address: str = "", source: str = ""
    ) -> Any:
        """2.3 Tạo đơn hàng."""
        return self._request(
            "POST",
            "/api/ords/create",
            {
                "PhoneNumber": phone_number,
                "CustomerName": customer_name,
                "Address": address,
                "Source": source,
            },
        )

    # ---- internals ----------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        body: Optional[dict] = None,
        auth: bool = True,
        retry_auth: bool = True,
    ) -> Any:
        if auth and not self.token:
            self.login()
        headers = {"Accept": "application/json"}
        if auth:
            headers["Authorization"] = f"Bearer {self.token}"
        raw = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            raw = json.dumps(body, ensure_ascii=False).encode("utf-8")

        status, text = self._transport(
            method, self.base_url + path, headers, raw, self.timeout
        )

        # Token expired/revoked: log in again once, if we have credentials.
        if status == 401 and auth and retry_auth and self.email and self.password:
            self.token = None
            return self._request(method, path, body, auth=True, retry_auth=False)

        try:
            data = json.loads(text) if text.strip() else None
        except ValueError:
            raise CRMError(
                f"{method} {path}: phản hồi không phải JSON (HTTP {status}).",
                status=status,
                payload=text[:500],
            )

        # The CRM reports some failures as HTTP 200 with "status_code" in the body.
        body_status = data.get("status_code") if isinstance(data, dict) else None
        failed = status >= 400 or (isinstance(body_status, int) and body_status >= 400)
        if failed:
            msg = None
            if isinstance(data, dict):
                msg = data.get("message") or data.get("error")
            raise CRMError(
                f"{method} {path}: {msg or 'lỗi'} (HTTP {status}"
                + (f", status_code {body_status}" if body_status else "")
                + ")",
                status=body_status or status,
                payload=data,
            )
        return data
