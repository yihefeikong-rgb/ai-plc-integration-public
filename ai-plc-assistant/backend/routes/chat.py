"""AI 对话路由 — LLM 调用 + RAG 知识库增强"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from llm.service import chat_with_fallback, PLC_SYSTEM_PROMPT
from routes import knowledge as kb_module

router = APIRouter()


class ChatRequest(BaseModel):
    model_id: str = "deepseek"
    messages: list[dict] = []
    temperature: float = 0.3
    max_tokens: int = 8192
    use_rag: bool = True  # 是否启用知识库检索增强


class ChatResponse(BaseModel):
    role: str = "assistant"
    content: str
    model: str = ""
    fallback: bool = False  # 是否切换了模型
    rag_sources: list[str] = []


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

    # 构建 system prompt
    system_prompt = PLC_SYSTEM_PROMPT
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
        # 替换已有的 system prompt，追加 RAG 上下文
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
