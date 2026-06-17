"""AI 对话路由 — LLM 调用 + RAG 知识库增强 + SSE 流式输出"""

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from llm.service import chat_with_fallback, chat_stream, get_available_providers, PLC_SYSTEM_PROMPT
from routes import knowledge as kb_module

router = APIRouter()


class ChatRequest(BaseModel):
    model_id: str = "deepseek"
    messages: list[dict] = []
    temperature: float = 0.3
    max_tokens: int = 8192
    use_rag: bool = True
    project_context: dict = {}  # 当前项目属性 {plc_type, tia_version, language, name}


class ChatResponse(BaseModel):
    role: str = "assistant"
    content: str
    model: str = ""
    fallback: bool = False  # 是否切换了模型
    rag_sources: list[str] = []


def _inject_project_context(base_prompt: str, project_context: dict) -> str:
    """将项目属性注入系统提示词"""
    if not project_context:
        return base_prompt
    parts = []
    if project_context.get("name"): parts.append(f"项目名称: {project_context['name']}")
    if project_context.get("plc_type"): parts.append(f"PLC型号: {project_context['plc_type']}")
    if project_context.get("tia_version"): parts.append(f"TIA版本: {project_context['tia_version']}")
    if project_context.get("language"): parts.append(f"编程语言: {project_context['language']}")
    if parts:
        return base_prompt + "\n\n## 当前项目配置\n" + "\n".join(parts) + "\n请严格按照以上项目配置生成代码。"
    return base_prompt


def _rag_search(query: str, top_k: int = 3) -> tuple[str, list[str]]:
    """从知识库检索相关内容，返回 (上下文文本, 来源列表)"""
    engine = kb_module.engine
    if engine is None:
        return "", []

    try:
        results = engine.search(query, top_k=top_k)
    except Exception:
        return "", []

    if not results:
        return "", []

    context_parts = []
    sources = []
    for r in results:
        score = r.get("score", 0)
        if score < 30:
            continue
        text = r["text"][:500]
        filename = r.get("filename", "unknown")
        context_parts.append(f"[来源: {filename}]\n{text}")
        if filename not in sources:
            sources.append(filename)

    if not context_parts:
        return "", []

    context = "\n\n---\n\n".join(context_parts)
    return context, sources


@router.post("", response_model=ChatResponse)
async def chat_with_llm(request: ChatRequest):
    """发送消息给 AI 模型，可选 RAG 增强"""
    if not request.messages:
        raise HTTPException(status_code=400, detail="消息列表不能为空")

    messages = list(request.messages)
    rag_sources = []

    # RAG: 用最后一条用户消息检索知识库
    rag_context = ""
    if request.use_rag:
        last_user = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user = m.get("content", "")
                break
        if last_user:
            rag_context, rag_sources = _rag_search(last_user)

    # 构建 system prompt（含项目上下文）
    system_prompt = _inject_project_context(PLC_SYSTEM_PROMPT, request.project_context)
    if rag_context:
        system_prompt += (
            "\n\n## 参考资料（来自本地知识库）\n"
            "以下是从用户知识库中检索到的相关内容，请在回答时参考：\n\n"
            f"{rag_context}"
        )

    # 确保 system prompt 在最前面
    has_system = any(m.get("role") == "system" for m in messages)
    if not has_system:
        messages.insert(0, {"role": "system", "content": system_prompt})
    elif rag_context:
        for i, m in enumerate(messages):
            if m.get("role") == "system":
                messages[i] = {"role": "system", "content": m["content"] + "\n\n" + rag_context}
                break

    try:
        result = chat_with_fallback(
            model_id=request.model_id,
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        return ChatResponse(
            content=result["content"],
            model=result["model"],
            fallback=result["fallback"],
            rag_sources=rag_sources,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"模型调用失败: {str(e)}")


@router.post("/stream")
async def chat_stream_endpoint(request: ChatRequest):
    """SSE 流式对话 — 逐 token 返回"""
    if not request.messages:
        raise HTTPException(status_code=400, detail="消息列表不能为空")

    messages = list(request.messages)
    rag_sources = []

    # RAG 增强（与非流式相同）
    rag_context = ""
    if request.use_rag:
        last_user = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user = m.get("content", "")
                break
        if last_user:
            rag_context, rag_sources = _rag_search(last_user)

    # system prompt（含项目上下文）
    system_prompt = _inject_project_context(PLC_SYSTEM_PROMPT, request.project_context)
    if rag_context:
        system_prompt += (
            "\n\n## 参考资料（来自本地知识库）\n"
            "以下是从用户知识库中检索到的相关内容，请在回答时参考：\n\n"
            f"{rag_context}"
        )
    has_system = any(m.get("role") == "system" for m in messages)
    if not has_system:
        messages.insert(0, {"role": "system", "content": system_prompt})
    elif rag_context:
        for i, m in enumerate(messages):
            if m.get("role") == "system":
                messages[i] = {"role": "system", "content": m["content"] + "\n\n" + rag_context}
                break

    def _sse(data: dict) -> str:
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    def event_generator():
        model_id = request.model_id
        fallback = False

        # 先发 RAG 源
        if rag_sources:
            yield _sse({"rag_sources": rag_sources})

        # 尝试主模型
        try:
            for token in chat_stream(model_id, messages, request.temperature, request.max_tokens):
                yield _sse({"token": token})
        except Exception as primary_err:
            # 主模型失败 → 尝试 fallback
            available = get_available_providers()
            provider_map = {"deepseek": "deepseek", "openai": "openai", "kimi": "kimi", "claude": "claude", "custom": "custom"}
            tried = {provider_map.get(model_id, model_id)}
            success = False

            for provider in available:
                if provider in tried:
                    continue
                tried.add(provider)
                try:
                    model_id = provider
                    fallback = True
                    for token in chat_stream(provider, messages, request.temperature, request.max_tokens):
                        yield _sse({"token": token})
                    success = True
                    break
                except Exception:
                    continue

            if not success:
                yield _sse({"error": f"所有模型调用均失败: {str(primary_err)}"})
                yield "data: [DONE]\n\n"
                return

        yield _sse({"done": True, "model": model_id, "fallback": fallback})
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
