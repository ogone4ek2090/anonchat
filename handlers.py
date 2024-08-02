from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from slowapi import Limiter
from slowapi.util import get_remote_address

from uuid import uuid1
from typing import List
from database import jwt_utils as jwt


limiter = Limiter(key_func=get_remote_address)
templates = Jinja2Templates("templates")

router = APIRouter()

class AnonChatManager:
    def __init__(self):
        self.active_connects: List[List[WebSocket]] = []
        self.waiting: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.receive()

        self.waiting.append(websocket)
        if len(self.waiting) == 2:
            (self.send(conn, "companion is founded!") for conn in self.waiting)
            self.active_connects.append(self.waiting)
            self.waiting.clear()

    def disconnect(self, websocket):
        for index, (conn1, conn2) in enumerate(self.active_connects):
            if websocket == conn1:
                self.send(conn2, "companion_leave_you")
            elif websocket == conn2:
                self.send(conn1, "companion_leave_you")
            else:
                continue
            del self.active_connects[index]

    def disconnect_from_waiting(self, websocket):
        if websocket in self.waiting:
            self.waiting.remove(websocket)

    async def send(websocket: WebSocket, text: str):
        await websocket.send_text(text)

    def send_companion(self, websocket, text):
        for conn1, conn2 in self.active_connects:
            if websocket == conn1:
                self.send(conn2, text)
            if websocket == conn2:
                self.send(conn1, text)



@router.get("/")
async def main_page(request: Request):
    response = templates.TemplateResponse(request, "index.html")
    print(request.client.host, sep="\n")
    return response


@router.get("/connect")
@limiter.limit("60/minute")
async def connect(request: Request, name: str = "DEFAULT"):
    uuid = uuid1()
    response = RedirectResponse("/")
    response.set_cookie("Authorization", jwt.gen_jwt(name=name, id=uuid))
    return response


@router.get("/chat")
@limiter.limit("60/minute")
async def chat(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="chat.html",
        context=jwt.decode_jwt(request.cookies.get("Authorization"))
    )


manager = AnonChatManager()


@router.websocket("/ws")
async def websocket_connect(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.send_companion(f"СОБЕСЕДНИК: {data}", websocket)
            await manager.send(f"ВЫ: {data}", websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)