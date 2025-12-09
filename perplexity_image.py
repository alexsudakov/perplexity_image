import re
import aiohttp
import pyscript  # для доступа к pyscript.config

IMAGE_URL_RE = re.compile(
    r"https?://\S+\.(?:png|jpg|jpeg|webp|gif)",
    re.IGNORECASE,
)


def _extract_image_url(data: dict) -> str | None:
    # 1. Top-level images
    images = data.get("images")
    if isinstance(images, list) and images:
        first = images[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            for key in ("imageUrl", "image_url", "url", "source"):
                if key in first:
                    return first[key]

    # 2. Top-level media / media_results
    media = data.get("media") or data.get("media_results")
    if isinstance(media, list) and media:
        first = media[0]
        if isinstance(first, dict):
            for key in ("imageUrl", "image_url", "url", "source"):
                if key in first:
                    return first[key]

    # 3. providerMetadata.perplexity.images
    md = data.get("providerMetadata") or data.get("provider_metadata")
    if isinstance(md, dict):
        perp = md.get("perplexity") or md.get("pplx")
        if isinstance(perp, dict):
            imgs = perp.get("images")
            if isinstance(imgs, list) and imgs:
                first = imgs[0]
                if isinstance(first, dict):
                    for key in ("imageUrl", "image_url", "url"):
                        if key in first:
                            return first[key]

    # 4. choices[0].message.content + поиск URL в тексте
    try:
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            msg = choices[0].get("message") if isinstance(choices[0], dict) else None
            if isinstance(msg, dict):
                content = msg.get("content")
                text = None
                if isinstance(content, str):
                    text = content
                elif isinstance(content, list):
                    parts = []
                    for part in content:
                        if isinstance(part, dict) and isinstance(part.get("text"), str):
                            parts.append(part["text"])
                    if parts:
                        text = "\n".join(parts)
                if text:
                    m = IMAGE_URL_RE.search(text)
                    if m:
                        return m.group(0)
    except Exception as e:
        log.error(f"perplexity_generate_image: error while parsing choices: {e}")

    return None


@service(supports_response="only")
async def perplexity_generate_image(prompt: str | None = None):
    """
    Генерация/поиск картинки через Perplexity Chat Completions API.

    :param prompt: текстовый запрос пользователя.
    :return: dict, доступный как response в Dev Tools и через response_variable.
    """
    entity_id = "input_text.perplexity_image_url"

    if not prompt or not isinstance(prompt, str):
        msg = "prompt is required and must be a non-empty string"
        log.error(f"perplexity_generate_image: {msg}")
        return {
            "ok": False,
            "error": msg,
            "image_url": state.get(entity_id, default=None),
            "entity_id": entity_id,
        }

    api_key = "<<YOUR_API_KEY>>"

    if not api_key:
        msg = "API key is not configured (global.perplexity_api_key in pyscript/config.yaml)"
        log.error(f"perplexity_generate_image: {msg}")
        return {
            "ok": False,
            "error": msg,
            "image_url": state.get(entity_id, default=None),
            "entity_id": entity_id,
        }

    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "sonar-pro",
        "messages": [
            {"role": "user", "content": prompt},
        ],
        "media_response": {
            "enable": True,
            "overrides": {
                "return_images": True,
            },
        },
        "return_images": True,
    }

    log.info("perplexity_generate_image: sending request to Perplexity")

    try:
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                status = resp.status
                if status != 200:
                    text = await resp.text()
                    msg = f"HTTP {status} from Perplexity; body: {text[:500]}"
                    log.error(f"perplexity_generate_image: {msg}")
                    return {
                        "ok": False,
                        "error": msg,
                        "image_url": state.get(entity_id, default=None),
                        "entity_id": entity_id,
                    }

                try:
                    data = await resp.json()
                except Exception as e:
                    text = await resp.text()
                    msg = f"JSON decode error: {e}; body: {text[:500]}"
                    log.error(f"perplexity_generate_image: {msg}")
                    return {
                        "ok": False,
                        "error": msg,
                        "image_url": state.get(entity_id, default=None),
                        "entity_id": entity_id,
                    }

    except Exception as e:
        msg = f"request failed: {e}"
        log.error(f"perplexity_generate_image: {msg}")
        return {
            "ok": False,
            "error": msg,
            "image_url": state.get(entity_id, default=None),
            "entity_id": entity_id,
        }

    image_url = _extract_image_url(data)

    if not image_url:
        msg = "Perplexity response has no image URL; keeping existing entity value"
        log.warning(f"perplexity_generate_image: {msg}")
        return {
            "ok": False,
            "error": msg,
            "image_url": state.get(entity_id, default=None),
            "entity_id": entity_id,
        }

    # финальный успешный ответ — всегда dict
    return {
        "ok": True,
        "image_url": image_url,
        "entity_id": entity_id,
        "prompt": prompt,
    }
