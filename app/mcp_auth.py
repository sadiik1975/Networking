"""ASGI wrapper that protects the hosted MCP endpoint with a shared secret."""
import hmac

from app.config import settings


class McpAuthMiddleware:
    """Accepts `Authorization: Bearer <key>` or `X-API-Key: <key>`; fails closed if no key is set."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        expected = settings.mcp_api_key
        if not expected:
            await self._reject(send, 503, b"MCP_API_KEY is not configured")
            return

        headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
        supplied = headers.get("x-api-key", "")
        auth = headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            supplied = auth[7:].strip()

        if not hmac.compare_digest(supplied.encode(), expected.encode()):
            await self._reject(send, 401, b"Invalid or missing MCP credentials")
            return
        await self.app(scope, receive, send)

    @staticmethod
    async def _reject(send, status: int, body: bytes):
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"text/plain"), (b"content-length", str(len(body)).encode())],
        })
        await send({"type": "http.response.body", "body": body})
