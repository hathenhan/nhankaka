import json
import unittest

from toshiko_crm import CRMError, ToshikoCRM


class FakeCRM:
    """Stands in for the HTTP layer and records every call."""

    def __init__(self, routes):
        self.routes = routes  # (method, path) -> list of (status, body) or one tuple
        self.calls = []

    def __call__(self, method, url, headers, body, timeout):
        path = url.replace("https://crm.test", "")
        self.calls.append(
            (method, path, headers, json.loads(body) if body else None)
        )
        answer = self.routes[(method, path)]
        if isinstance(answer, list):
            answer = answer.pop(0)
        status, payload = answer
        return status, payload if isinstance(payload, str) else json.dumps(payload)


LOGIN_OK = (200, {"status_code": 200, "access_token": "tok-1", "token_type": "Bearer"})


def make(routes, **kw):
    fake = FakeCRM(routes)
    kw.setdefault("email", "a@b.c")
    kw.setdefault("password", "pw")
    return ToshikoCRM(base_url="https://crm.test/", transport=fake, **kw), fake


class ClientTest(unittest.TestCase):
    def test_login_stores_token(self):
        crm, fake = make({("POST", "/api/login"): LOGIN_OK})
        self.assertEqual(crm.login(), "tok-1")
        method, path, headers, body = fake.calls[0]
        self.assertEqual(body, {"email": "a@b.c", "password": "pw"})
        self.assertNotIn("Authorization", headers)

    def test_login_failure_in_body_raises(self):
        # The real server answers HTTP 200 with status_code 500 in the body.
        crm, _ = make(
            {("POST", "/api/login"): (200, {"status_code": 500, "message": "Unauthorized"})}
        )
        with self.assertRaises(CRMError) as ctx:
            crm.login()
        self.assertEqual(ctx.exception.status, 500)
        self.assertIn("Unauthorized", str(ctx.exception))
        self.assertIsNone(crm.token)

    def test_get_order_logs_in_first_and_sends_bearer(self):
        crm, fake = make(
            {
                ("POST", "/api/login"): LOGIN_OK,
                ("GET", "/api/ords/detail/535155"): (200, {"id": 535155}),
            }
        )
        self.assertEqual(crm.get_order(535155), {"id": 535155})
        self.assertEqual(fake.calls[1][2]["Authorization"], "Bearer tok-1")

    def test_assign_sale(self):
        crm, fake = make(
            {("PUT", "/api/ords/assign/535155/sale"): (200, {"ok": True})}, token="t"
        )
        crm.assign_sale(535155, 33)
        self.assertEqual(fake.calls[0][3], {"id": 33})

    def test_create_order_body(self):
        crm, fake = make({("POST", "/api/ords/create"): (200, {"id": 1})}, token="t")
        crm.create_order("0983609090", "Lê Đặng Nguyên", "Hà Nội", "FB")
        self.assertEqual(
            fake.calls[0][3],
            {
                "PhoneNumber": "0983609090",
                "CustomerName": "Lê Đặng Nguyên",
                "Address": "Hà Nội",
                "Source": "FB",
            },
        )

    def test_expired_token_relogs_in_once(self):
        crm, fake = make(
            {
                ("POST", "/api/login"): LOGIN_OK,
                ("GET", "/api/ords/detail/1"): [
                    (401, {"success": False, "error": "Access denied."}),
                    (200, {"id": 1}),
                ],
            },
            token="old",
        )
        self.assertEqual(crm.get_order(1), {"id": 1})
        self.assertEqual(fake.calls[-1][2]["Authorization"], "Bearer tok-1")

    def test_404_raises_with_server_message(self):
        crm, _ = make(
            {("GET", "/api/ords/detail/9"): (404, {"message": "not found"})}, token="t"
        )
        with self.assertRaises(CRMError) as ctx:
            crm.get_order(9)
        self.assertEqual(ctx.exception.status, 404)

    def test_missing_credentials(self):
        fake = FakeCRM({})
        crm = ToshikoCRM(base_url="https://crm.test", transport=fake)
        crm.email = crm.password = crm.token = None
        with self.assertRaises(CRMError):
            crm.get_order(1)
        self.assertEqual(fake.calls, [])


if __name__ == "__main__":
    unittest.main()
