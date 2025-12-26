
from __future__ import annotations
from typing import Optional, Callable, Dict, Any
import os
import json

time_out = 60


def resolve_env(value: str) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if s.startswith("$") and len(s) > 1:
        return os.environ.get(s[1:].strip(), "").strip()
    return s


class BaseLLMClient:
    def __init__(self):
        self._debug_hook: Optional[Callable[[Dict[str, Any]], None]] = None

    def set_debug_hook(self, hook: Optional[Callable[[Dict[str, Any]], None]]):
        self._debug_hook = hook

    def _emit_debug(self, data: Dict[str, Any]):
        try:
            if self._debug_hook:
                self._debug_hook(data)
        except Exception:
            pass

    
    def build_request(
        self,
        history_text: str,
        new_incoming: str,
        persona_text: str = "",
        split_delimiter: str = "<<<NEXT>>>",
    ) -> Dict[str, Any]:
        raise NotImplementedError()

    def generate_reply(
        self,
        history_text: str,
        new_incoming: str,
        persona_text: str = "",
        split_delimiter: str = "<<<NEXT>>>",
    ) -> str:
        raise NotImplementedError()


class MockLLMClient(BaseLLMClient):
    def __init__(self):
        super().__init__()

    def build_request(
        self,
        history_text: str,
        new_incoming: str,
        persona_text: str = "",
        split_delimiter: str = "<<<NEXT>>>",
    ) -> Dict[str, Any]:
        system_final = "MOCK SYSTEM"
        user_prompt = f"MOCK USER\nincoming={new_incoming}"
        payload = {"mock": True}

        return {
            "provider": "mock",
            "system": system_final,
            "user": user_prompt,
            "payload": payload,
            "url": "",
            "headers": {},
            "meta": {"provider": "mock", "split_delimiter": split_delimiter},
            "inputs": {
                "history": history_text,
                "incoming": new_incoming,
                "persona": persona_text,
            },
        }

    def generate_reply(
        self,
        history_text: str,
        new_incoming: str,
        persona_text: str = "",
        split_delimiter: str = "<<<NEXT>>>",
    ) -> str:
        req = self.build_request(history_text, new_incoming, persona_text, split_delimiter)

        raw = f"收到：{new_incoming[:40]}{split_delimiter}我先去看看~"

        
        self._emit_debug(
            {
                "phase": "pre_request",
                "system": req["system"],
                "user": req["user"],
                "payload": req["payload"],
                "meta": req.get("meta", {}),
            }
        )

        
        self._emit_debug(
            {
                "phase": "post_response",
                "raw_output": raw,
                "split_delimiter": split_delimiter,
                "parts": [p.strip() for p in raw.split(split_delimiter) if p.strip()],
                "meta": {"provider": "mock"},
            }
        )
        return raw


class OpenAIClient(BaseLLMClient):
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float,
        system_prompt: str,
        user_template: str,
    ):
        super().__init__()
        self.api_key_raw = api_key
        self.base_url_raw = base_url
        self.model_raw = model
        self.temperature = float(temperature)
        self.system_prompt_raw = system_prompt
        self.user_template_raw = user_template

    def _resolved(self):
        api_key = resolve_env(self.api_key_raw)
        base_url = resolve_env(self.base_url_raw).rstrip("/")
        model = resolve_env(self.model_raw)
        system_prompt = resolve_env(self.system_prompt_raw)
        user_template = resolve_env(self.user_template_raw)
        return api_key, base_url, model, system_prompt, user_template

    def _build_split_rules(self, split_delimiter: str) -> str:
        d = (split_delimiter or "").strip()
        if not d:
            return ""
        return (
            "【输出格式规则】\n"
            "- 你的最终输出只能是“回复文本”，不要加前缀/解释/markdown。\n"
            "- 你可以输出 1 条或多条消息。\n"
            f"- 如果输出多条消息：必须用分隔符 {d} 分隔各条消息。\n"
            "- 分隔符不要出现在开头或结尾。\n"
            f"- 示例：你好{d}最近咋样？\n"
        )

    def build_request(
        self,
        history_text: str,
        new_incoming: str,
        persona_text: str = "",
        split_delimiter: str = "<<<NEXT>>>",
    ) -> Dict[str, Any]:
        api_key, base_url, model, system_prompt, user_template = self._resolved()

        if not api_key:
            return {"error": "（未设置 OpenAI API Key：请在设置里填入 Key 或 $ENV_VAR）"}
        if not base_url:
            return {"error": "（Base URL 为空）"}
        if not model:
            return {"error": "（Model 为空）"}
        if not user_template.strip():
            user_template = "{incoming}"

        split_rules = self._build_split_rules(split_delimiter)

        sys_parts = [system_prompt.strip() or "You are a helpful assistant."]
        if persona_text.strip():
            sys_parts.append("【人格设定】\n" + persona_text.strip())
        if split_rules:
            sys_parts.append(split_rules)

        system_final = "\n\n".join(sys_parts)

        try:
            user_prompt = user_template.format(history=history_text, incoming=new_incoming)
        except Exception as e:
            return {"error": f"（User Template 格式化失败：{e}）"}

        if split_rules:
            user_prompt = user_prompt + "\n\n【再次强调输出格式】\n" + split_rules

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_final},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
        }

        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {'****' + api_key[-4:] if api_key else ''}",
            "Content-Type": "application/json",
        }

        return {
            "provider": "openai",
            "system": system_final,
            "user": user_prompt,
            "payload": payload,
            "url": url,
            "headers": headers,
            "meta": {
                "provider": "openai",
                "base_url": base_url,
                "model": model,
                "temperature": self.temperature,
                "split_delimiter": split_delimiter,
                "persona_attached": bool(persona_text.strip()),
                "api_key_hint": ("****" + api_key[-4:]) if api_key else "",
            },
            "inputs": {
                "history": history_text,
                "incoming": new_incoming,
                "persona": persona_text,
            },
        }

    def generate_reply(
        self,
        history_text: str,
        new_incoming: str,
        persona_text: str = "",
        split_delimiter: str = "<<<NEXT>>>",
    ) -> str:
        req = self.build_request(history_text, new_incoming, persona_text, split_delimiter)
        if "error" in req:
            return str(req["error"])

        
        self._emit_debug(
            {
                "phase": "pre_request",
                "system": req["system"],
                "user": req["user"],
                "payload": req["payload"],
                "meta": req.get("meta", {}),
                "url": req.get("url", ""),
                "headers": req.get("headers", {}),
            }
        )

        payload = req["payload"]
        
        api_key_real = resolve_env(self.api_key_raw)
        url_real = req["url"]

        
        try:
            import requests

            r = requests.post(
                url_real,
                headers={"Authorization": f"Bearer {api_key_real}", "Content-Type": "application/json"},
                data=json.dumps(payload, ensure_ascii=False),
            )
            r.raise_for_status()
            data = r.json()

            raw = (data.get("choices", [{}])[0].get("message", {}).get("content") or "")
            raw = str(raw)

            finish_reason = data.get("choices", [{}])[0].get("finish_reason", "")
            usage = data.get("usage", {})

            self._emit_debug(
                {
                    "phase": "post_response",
                    "raw_output": raw,
                    "finish_reason": finish_reason,
                    "usage": usage,
                    "parts": [p.strip() for p in raw.split(split_delimiter) if p.strip()]
                    if split_delimiter
                    else [raw.strip()],
                    "raw_response": data,
                }
            )
            return raw.strip()

        except Exception as e_req:
            
            try:
                import urllib.request

                req_u = urllib.request.Request(
                    url_real,
                    data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    headers={"Authorization": f"Bearer {api_key_real}", "Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req_u, time_out) as resp:
                    data = json.loads(resp.read().decode("utf-8"))

                raw = (data.get("choices", [{}])[0].get("message", {}).get("content") or "")
                raw = str(raw)

                finish_reason = data.get("choices", [{}])[0].get("finish_reason", "")
                usage = data.get("usage", {})

                self._emit_debug(
                    {
                        "phase": "post_response",
                        "raw_output": raw,
                        "finish_reason": finish_reason,
                        "usage": usage,
                        "parts": [p.strip() for p in raw.split(split_delimiter) if p.strip()]
                        if split_delimiter
                        else [raw.strip()],
                        "raw_response": data,
                        "meta": {"fallback": "urllib", "error": str(e_req)},
                    }
                )
                return raw.strip()

            except Exception as e:
                self._emit_debug(
                    {"phase": "error", "error": str(e), "meta": {"fallback": "urllib", "error_prev": str(e_req)}}
                )
                return f"（AI 请求失败：{e}）"


class SiliconFlowClient(BaseLLMClient):
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float,
        system_prompt: str,
        user_template: str,
    ):
        super().__init__()
        self.api_key_raw = api_key
        self.base_url_raw = base_url
        self.model_raw = model
        self.temperature = float(temperature)
        self.system_prompt_raw = system_prompt
        self.user_template_raw = user_template

    def _resolved(self):
        api_key = resolve_env(self.api_key_raw)
        base_url = resolve_env(self.base_url_raw).rstrip("/")
        model = resolve_env(self.model_raw)
        system_prompt = resolve_env(self.system_prompt_raw)
        user_template = resolve_env(self.user_template_raw)
        return api_key, base_url, model, system_prompt, user_template

    def _build_split_rules(self, split_delimiter: str) -> str:
        d = (split_delimiter or "").strip()
        if not d:
            return ""
        return (
            "【输出格式规则】\n"
            "- 你的最终输出只能是“回复文本”，不要加前缀/解释/markdown。\n"
            "- 你可以输出 1 条或多条消息。\n"
            f"- 如果输出多条消息：必须用分隔符 {d} 分隔各条消息。\n"
            "- 分隔符不要出现在开头或结尾。\n"
            f"- 示例：你好{d}最近咋样？\n"
        )

    def build_request(
        self,
        history_text: str,
        new_incoming: str,
        persona_text: str = "",
        split_delimiter: str = "<<<NEXT>>>",
    ) -> Dict[str, Any]:
        api_key, base_url, model, system_prompt, user_template = self._resolved()

        if not api_key:
            return {"error": "（未设置 SiliconFlow API Key：请在设置里填入 Key 或 $ENV_VAR）"}
        if not base_url:
            base_url = "https://api.siliconflow.cn/v1"  # 默认硅基流动API地址
        if not model:
            model = "Qwen/Qwen2.5-72B-Instruct"  # 默认硅基流动模型
        if not user_template.strip():
            user_template = "{incoming}"

        split_rules = self._build_split_rules(split_delimiter)

        sys_parts = [system_prompt.strip() or "You are a helpful assistant."]
        if persona_text.strip():
            sys_parts.append("【人格设定】\n" + persona_text.strip())
        if split_rules:
            sys_parts.append(split_rules)

        system_final = "\n\n".join(sys_parts)

        try:
            user_prompt = user_template.format(history=history_text, incoming=new_incoming)
        except Exception as e:
            return {"error": f"（User Template 格式化失败：{e}）"}

        if split_rules:
            user_prompt = user_prompt + "\n\n【再次强调输出格式】\n" + split_rules

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_final},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
        }

        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {'****' + api_key[-4:] if api_key else ''}",
            "Content-Type": "application/json",
        }

        return {
            "provider": "siliconflow",
            "system": system_final,
            "user": user_prompt,
            "payload": payload,
            "url": url,
            "headers": headers,
            "meta": {
                "provider": "siliconflow",
                "base_url": base_url,
                "model": model,
                "temperature": self.temperature,
                "split_delimiter": split_delimiter,
                "persona_attached": bool(persona_text.strip()),
                "api_key_hint": ("****" + api_key[-4:]) if api_key else "",
            },
            "inputs": {
                "history": history_text,
                "incoming": new_incoming,
                "persona": persona_text,
            },
        }

    def generate_reply(
        self,
        history_text: str,
        new_incoming: str,
        persona_text: str = "",
        split_delimiter: str = "<<<NEXT>>>",
    ) -> str:
        req = self.build_request(history_text, new_incoming, persona_text, split_delimiter)
        if "error" in req:
            return str(req["error"])

        self._emit_debug(
            {
                "phase": "pre_request",
                "system": req["system"],
                "user": req["user"],
                "payload": req["payload"],
                "meta": req.get("meta", {}),
                "url": req.get("url", ""),
                "headers": req.get("headers", {}),
            }
        )

        payload = req["payload"]
        api_key_real = resolve_env(self.api_key_raw)
        url_real = req["url"]

        try:
            import requests

            r = requests.post(
                url_real,
                headers={"Authorization": f"Bearer {api_key_real}", "Content-Type": "application/json"},
                data=json.dumps(payload, ensure_ascii=False),
            )
            r.raise_for_status()
            data = r.json()

            raw = (data.get("choices", [{}])[0].get("message", {}).get("content") or "")
            raw = str(raw)

            finish_reason = data.get("choices", [{}])[0].get("finish_reason", "")
            usage = data.get("usage", {})

            self._emit_debug(
                {
                    "phase": "post_response",
                    "raw_output": raw,
                    "finish_reason": finish_reason,
                    "usage": usage,
                    "parts": [p.strip() for p in raw.split(split_delimiter) if p.strip()]
                    if split_delimiter
                    else [raw.strip()],
                    "raw_response": data,
                }
            )
            return raw.strip()

        except Exception as e_req:
            try:
                import urllib.request

                req_u = urllib.request.Request(
                    url_real,
                    data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    headers={"Authorization": f"Bearer {api_key_real}", "Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req_u, time_out) as resp:
                    data = json.loads(resp.read().decode("utf-8"))

                raw = (data.get("choices", [{}])[0].get("message", {}).get("content") or "")
                raw = str(raw)

                finish_reason = data.get("choices", [{}])[0].get("finish_reason", "")
                usage = data.get("usage", {})

                self._emit_debug(
                    {
                        "phase": "post_response",
                        "raw_output": raw,
                        "finish_reason": finish_reason,
                        "usage": usage,
                        "parts": [p.strip() for p in raw.split(split_delimiter) if p.strip()]
                        if split_delimiter
                        else [raw.strip()],
                        "raw_response": data,
                        "meta": {"fallback": "urllib", "error": str(e_req)},
                    }
                )
                return raw.strip()

            except Exception as e:
                self._emit_debug(
                    {"phase": "error", "error": str(e), "meta": {"fallback": "urllib", "error_prev": str(e_req)}}
                )
                return f"（AI 请求失败：{e}）"
