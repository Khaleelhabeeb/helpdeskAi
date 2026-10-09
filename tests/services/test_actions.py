import json
from types import SimpleNamespace

import pytest

from services import actions as A
from services import rag_service


def _action(**kw):
    base = dict(
        id="1", name="get_order", description="Look up an order", method="GET",
        url="https://api.example.com/orders/{order_id}",
        parameters=[
            {"name": "order_id", "type": "string", "description": "", "required": True},
            {"name": "verbose", "type": "boolean", "description": "", "required": False},
        ],
    )
    base.update(kw)
    return A.RuntimeAction(**base)


# ── validation ──

def test_name_rules():
    assert A.validate_action_name("Get_Order") == "get_order"
    for bad in ["ab", "1abc", "has-dash", "transfer_to_human"]:
        with pytest.raises(A.ActionValidationError):
            A.validate_action_name(bad)


def test_url_rejects_placeholder_in_host_and_unknown_params():
    params = A.validate_parameters([{"name": "id", "type": "string"}])
    assert A.validate_url_template("https://api.x.com/a/{id}", params)
    for bad in ["https://{id}.x.com/a", "https://api.x.com/{nope}", "ftp://x.com", "https://u:p@x.com/a"]:
        with pytest.raises(A.ActionValidationError):
            A.validate_url_template(bad, params)


def test_headers_mask_keeps_existing_secret():
    blob = A.encrypt_headers({"Authorization": "Bearer s3cret"})
    assert A.masked_headers(blob) == [{"name": "Authorization", "value": A.HEADER_MASK}]
    kept = A.validate_headers([{"name": "Authorization", "value": A.HEADER_MASK}], blob)
    assert kept == {"Authorization": "Bearer s3cret"}
    with pytest.raises(A.ActionValidationError):
        A.validate_headers([{"name": "X-New", "value": A.HEADER_MASK}], blob)
    with pytest.raises(A.ActionValidationError):
        A.validate_headers([{"name": "Host", "value": "evil"}], None)


# ── request building ──

def test_build_request_get_puts_path_and_query():
    url, query, body = A.build_request(_action(), {"order_id": "A 1/2", "verbose": "yes"})
    assert url == "https://api.example.com/orders/A%201%2F2"
    assert query == {"verbose": True}
    assert body is None


def test_build_request_post_uses_json_body():
    action = _action(method="POST", url="https://api.example.com/orders")
    url, query, body = A.build_request(action, {"order_id": "42"})
    assert query is None and body == {"order_id": "42"}


def test_build_request_missing_required():
    with pytest.raises(ValueError, match="order_id"):
        A.build_request(_action(), {})


# ── SSRF ──

@pytest.mark.anyio
@pytest.mark.parametrize("host", ["127.0.0.1", "10.0.0.5", "169.254.169.254", "localhost"])
async def test_private_hosts_blocked(host, monkeypatch):
    monkeypatch.delenv("ACTIONS_ALLOW_PRIVATE_NETWORKS", raising=False)
    result = await A.execute_action(_action(url=f"http://{host}/orders/{{order_id}}"), {"order_id": "1"})
    assert not result.ok and "private" in (result.error or "")


# ── tool loop ──

class _FakeCompletions:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def _tool_response(name, args):
    tc = SimpleNamespace(id="call_1", function=SimpleNamespace(name=name, arguments=json.dumps(args)))
    return SimpleNamespace(choices=[SimpleNamespace(finish_reason="tool_calls", message=SimpleNamespace(content=None, tool_calls=[tc]))])


def _text_response(text):
    return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=text, tool_calls=None))])


@pytest.mark.anyio
async def test_tool_loop_runs_action_then_answers(monkeypatch):
    fake = _FakeCompletions([_tool_response("get_order", {"order_id": "7"}), _text_response("Your order shipped.")])
    monkeypatch.setattr(rag_service, "get_async_groq_client", lambda: SimpleNamespace(chat=SimpleNamespace(completions=fake)))

    seen = []

    async def executor(name, args):
        seen.append((name, args))
        return json.dumps({"ok": True, "status": 200, "data": "shipped"})

    events = [e async for e in rag_service.astream_answer_with_tools("m", [{"role": "user", "content": "hi"}], [{}], executor=executor)]
    assert seen == [("get_order", {"order_id": "7"})]
    assert events[0] == {"type": "action", "name": "get_order", "ok": True}
    assert "".join(e["content"] for e in events if e["type"] == "token") == "Your order shipped."
    # Second call carries the tool result back to the model
    assert fake.calls[1]["messages"][-1]["role"] == "tool"


@pytest.mark.anyio
async def test_tool_loop_surfaces_unowned_tools(monkeypatch):
    fake = _FakeCompletions([_tool_response("transfer_to_human", {"reason": "x"})])
    monkeypatch.setattr(rag_service, "get_async_groq_client", lambda: SimpleNamespace(chat=SimpleNamespace(completions=fake)))

    async def executor(name, args):
        return None

    events = [e async for e in rag_service.astream_answer_with_tools("m", [], [{}], executor=executor)]
    assert events == [{"type": "tool_call", "name": "transfer_to_human", "arguments": {"reason": "x"}}]
