import json
import urllib.error
import urllib.request


LLAMA_SERVER_URL = "http://127.0.0.1:8081/v1/chat/completions"


class ModelService:
    def __init__(self):
        self.server_url = LLAMA_SERVER_URL

    def generate(
        self,
        prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.2
    ) -> str:

        prompt = prompt.strip()

        if not prompt:
            raise ValueError("Prompt cannot be empty.")

        payload = {
            "model": "deepresearch",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are DeepResearch, an academic research assistant. "
                        "Answer clearly, accurately, and concisely. "
                        "When research context is provided, base your answer "
                        "on that context. Do not invent unsupported facts."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        request = urllib.request.Request(
            self.server_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=180
            ) as response:
                data = json.loads(
                    response.read().decode("utf-8")
                )

        except urllib.error.URLError as exc:
            raise RuntimeError(
                "Local language model server is unavailable."
            ) from exc

        except TimeoutError as exc:
            raise RuntimeError(
                "Local language model generation timed out."
            ) from exc

        try:
            answer = data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(
                "Unexpected response from local language model."
            ) from exc

        if not answer:
            raise RuntimeError(
                "Local language model returned an empty response."
            )

        return answer
