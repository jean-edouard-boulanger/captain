from typing import Optional, Dict
from socketio import AsyncServer
import functools
import logging


logger = logging.getLogger("socketio_rpc")


class SocketioRpc(object):
    def __init__(self, socketio_server: AsyncServer):
        self._server = socketio_server
        self._server.on("rpc_request")(self._handle_rpc_request)
        self._handlers = {}

    async def _send_rpc_response(self, message_id: str, response: Optional[Dict] = None, error: Optional[str] = None):
        payload = {
            "message_id": message_id,
            "response": response,
            "error": error
        }
        logger.debug(f"sending rpc response: {payload}")
        await self._server.emit("rpc_response", payload)

    async def _handle_rpc_request(self, _, payload):
        logger.debug(f"handling rpc request: {payload}")
        message_id = payload["message_id"]
        request = payload["request"]
        request_type = list(request.keys())[0]
        handler = self._handlers.get(request_type)
        if handler is None:
            logger.debug(f"no handler defined for request type: {request_type}")
            return
        try:
            response = handler(message_id, request[request_type])
            await self._send_rpc_response(message_id, response=response)
        except Exception as e:
            await self._send_rpc_response(message_id, error=str(e))

    def on(self, request_type):
        def decorator(func):
            @functools.wraps(func)
            def impl(message_id, request):
                return func(message_id, request)
            self._handlers[request_type] = impl
            return impl
        return decorator
