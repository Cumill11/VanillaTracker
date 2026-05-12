from starlette.requests import Request


def add_message(request: Request, text: str) -> None:
    if "_messages" not in request.session:
        request.session["_messages"] = []
    request.session["_messages"].append(text)


def get_messages(request: Request) -> list[str]:
    msgs = request.session.pop("_messages", [])
    return msgs
