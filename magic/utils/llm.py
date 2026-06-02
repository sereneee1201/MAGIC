# -*- coding: utf-8 -*-

import json
import logging
import mimetypes
import re
import time
import warnings
from json.decoder import JSONDecodeError
from os.path import isfile
from typing import Annotated, Any, Literal, Optional, overload
from uuid import uuid4

import cv2
import json_repair
import numpy as np
from openai import NOT_GIVEN, OpenAI
from openai.types.chat import ChatCompletion, ChatCompletionTokenLogprob
from PIL import Image
from pydantic import BaseModel, Field, GetCoreSchemaHandler, HttpUrl
from pydantic_core import CoreSchema, core_schema
from pydantic_core.core_schema import dict_schema, list_schema, str_schema, union_schema
from termcolor import colored

from magic.utils.dtypes import ImgLike, JsonObject, NonEmptyStr, PathLike, SDict
from magic.utils.file import load_text_file
from magic.utils.misc import Timer, bytes_to_base64, colored_error, format_error, tsprint

httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.WARNING)


class LlmConfig(BaseModel, validate_assignment=True, strict=True):
    model: NonEmptyStr
    max_tokens: Annotated[int, Field(ge=1)] = 4096
    max_retries: Annotated[int, Field(ge=0)] = 5
    base_url: Optional[str] = None
    api_key: Optional[str] = None


class Messages(list):
    def add_system(self, prompt: str) -> None:
        self.append({"role": "system", "content": prompt})

    def add_user(self, prompt: str, images: Optional[list[ImgLike]] = None) -> None:
        content = [{"type": "text", "text": prompt}]
        if images is not None:
            for img in images:
                content.append({"type": "image_url", "image_url": {"url": self.__encode_image(img), "detail": "high"}})
        self.append({"role": "user", "content": content})

    def add_assistant(self, response: str) -> None:
        self.append({"role": "assistant", "content": response})

    def __encode_image(self, img: ImgLike) -> str:
        if isinstance(img, (Image.Image, np.ndarray)):
            if isinstance(img, Image.Image):
                img = np.array(img.convert("RGB"))
            else:
                assert len(img.shape) == 3 and img.shape[-1] == 3
            mime = "image/png"
            content = bytes_to_base64(cv2.imencode(".png", img)[1])
        elif isinstance(img, PathLike):
            mime, _ = mimetypes.guess_type(img)
            if not mime.startswith("image/"):
                raise ValueError(f"{img} is not an image")
            with open(img, "rb") as f:
                content = bytes_to_base64(f.read())
        else:
            raise TypeError(f"Unsupported image type '{type(img)}'")
        return f"data:{mime};base64,{content}"

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        schema = list_schema(
            items_schema=dict_schema(
                keys_schema=str_schema(),
                values_schema=union_schema(
                    [
                        str_schema(),
                        list_schema(
                            items_schema=dict_schema(
                                keys_schema=str_schema(),
                                values_schema=union_schema([str_schema(), dict_schema(str_schema(), str_schema())]),
                            )
                        ),
                    ]
                ),
            )
        )
        return core_schema.no_info_after_validator_function(cls, schema)


class LlmContent(BaseModel, validate_assignment=True, strict=True):
    model: str
    base_url: Optional[HttpUrl] = None
    max_tokens: Optional[Annotated[int, Field(ge=1)]] = None
    temperature: Optional[Annotated[float, Field(ge=0.0, le=2.0)]] = None
    duration: Optional[float] = None
    prompt_tokens: Optional[Annotated[int, Field(ge=1)]] = None
    completion_tokens: Optional[Annotated[int, Field(ge=1)]] = None
    messages: Optional[Messages] = None


class LlmOutput(BaseModel, validate_assignment=True, strict=True):
    response: str
    content: LlmContent
    logprobs: Optional[list[ChatCompletionTokenLogprob]] = None
    completion: ChatCompletion


class Llm(object):
    def __init__(
        self,
        config: LlmConfig,
        sys_prompt: Optional[str] = None,
        json_parser: Optional["JsonParser"] = None,
        verbose: bool = False,
    ) -> None:
        self.__config = config
        if sys_prompt is not None:
            sys_prompt = sys_prompt.strip()
            if sys_prompt == "":
                sys_prompt = None
            elif isfile(sys_prompt):
                sys_prompt = load_text_file(sys_prompt)
        self.__sys_prompt = sys_prompt
        self.__json_parser = JsonParser() if json_parser is None else json_parser
        self.__verbose = verbose

        self.__messages = Messages()
        self.clear_messages()

    def __call__(
        self,
        prompt: str,
        *,
        temperature: Optional[float] = None,
        images: Optional[list[ImgLike]] = None,
        **kwargs: Any,
    ) -> LlmOutput:
        """
        Invoke the LLM and get a text response.

        Args:
            prompt (str): Text input to the LLM.
            temperature (Optional[float], optional): A parameter determining the
                randomness of the response generated by the LLM. The higher the
                value, the more random the response. Defaults to None.

        Returns:
            tuple[str, LlmContent]: A 2-tuple, where the first element is the
                text response from the LLM, while the second element is the
                content from the LLM.
        """

        llm_content = LlmContent(
            model=self.config.model,
            base_url=self.config.base_url,
            max_tokens=self.config.max_tokens,
            temperature=temperature,
        )
        with Timer() as timer:
            client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=1800,
                max_retries=self.config.max_retries,
            )
            self.__messages.add_user(prompt, images=images)
            for r in range(self.config.max_retries + 1):
                try:
                    completion = client.chat.completions.create(
                        model=self.config.model,
                        messages=self.messages,
                        temperature=temperature,
                        max_tokens=self.config.max_tokens,
                        **({"logprobs": kwargs["logprobs"]} if "logprobs" in kwargs else {}),
                        **({"top_logprobs": kwargs["top_logprobs"]} if "top_logprobs" in kwargs else {}),
                        response_format={"type": "json_object"} if kwargs.get("return_json", False) else NOT_GIVEN,
                        reasoning_effort=kwargs.get("reasoning_effort", NOT_GIVEN),
                    )
                    choice = completion.choices[0]
                    response = choice.message.content
                    assert response is not None, "LLM response is None"
                    if choice.finish_reason != "stop":
                        warnings.warn(f"LLM didn't stop naturally, but at '{choice.finish_reason}'", UserWarning)
                    logprobs = None
                    if kwargs.get("logprobs", False):
                        logprobs = choice.logprobs.content
                        assert logprobs is not None, "LLM logprobs is None"
                except KeyboardInterrupt:
                    raise
                except BaseException as e:
                    if r == self.config.max_retries:
                        raise
                    chat_id = kwargs.get("chat_id", None)
                    delay = 10
                    tsprint(
                        colored_error(),
                        f"<{f'{chat_id}' if chat_id is not None else ''}@{r}>",
                        f"Sleeping {delay}s and retrying OpenAI.chat.completions.create():",
                        format_error(e)[0],
                        end="\n\n",
                    )
                    time.sleep(delay)
                    continue
                else:
                    break
            response = completion.choices[0].message.content
            self.__messages.add_assistant(response)
            duration = timer.get()
        llm_content.duration = duration
        llm_content.prompt_tokens = completion.usage.prompt_tokens
        llm_content.completion_tokens = completion.usage.completion_tokens
        llm_content.messages = self.messages
        return LlmOutput(response=response, content=llm_content, logprobs=logprobs, completion=completion)

    def clear_messages(self) -> None:
        self.__messages.clear()
        if self.sys_prompt is not None:
            self.__messages.add_system(self.sys_prompt)

    @overload
    def chat(
        self, prompt: str, *, temperature: Optional[float], to_json: Literal[False], **kwargs: Any
    ) -> tuple[str, LlmOutput]: ...

    @overload
    def chat(
        self, prompt: str, *, temperature: Optional[float], to_json: Literal[True], **kwargs: Any
    ) -> tuple[Optional[JsonObject], LlmOutput]: ...

    def chat(
        self, prompt: str, *, temperature: Optional[float] = None, to_json: bool = False, **kwargs: Any
    ) -> tuple[str | Optional[JsonObject], LlmOutput]:
        chat_id = uuid4().hex[:8]
        h = colored(f"<{chat_id}>", color="dark_grey")
        if self.__verbose:
            text = f"{h}\n{colored('User:', color='green')} {prompt}"
            tsprint("-" * 40, text, "=" * 40, sep="\n", end="\n\n")
        for r in range(self.config.max_retries + 1):
            output = self.__call__(prompt, temperature=temperature, chat_id=chat_id, **kwargs)
            if to_json:
                try:
                    response = self.__json_parser(output.response)
                except KeyboardInterrupt:
                    raise
                except BaseException as e:
                    if r == self.config.max_retries:
                        raise
                    tsprint(colored_error(), f"<{chat_id}@{r}>", format_error(e)[0], end="\n\n")
                    continue
                else:
                    break
            else:
                response = output.response
                break
        if self.__verbose:
            text = f"{h}\n{colored(f'LLM ({round(output.content.duration, 1)}s):', color='magenta')} {response}"
            tsprint("-" * 40, text, "=" * 40, sep="\n", end="\n\n")
        return response, output

    @property
    def config(self) -> LlmConfig:
        return self.__config

    @property
    def sys_prompt(self) -> Optional[str]:
        return self.__sys_prompt

    @property
    def messages(self) -> Messages:
        return self.__messages


class TemplateFormatter(object):
    def __init__(self, template: str, **variables: Any) -> None:
        """
        Args:
            template (str): A string whose instances of "{...}" will be
                substituted accordingly upon invocation of the `__call__()`
                method. If you want to escape some pairs of "{...}", use
                "{{...}}" instead.
            variables (Optional[SDict[Any]], optional): Names of placeholders
                which will be substituted upon invocation of the `__call__()`
                method. Defaults to None.

                If `template` contains "{year}", and you want to give it a
                default value of `2024`, then you should pass:

                ```python
                {"year": 2024}
                ```

                But if "{year}" is not optional, then you must use `None`:

                ```python
                {"year": None}
                ```
        """

        self.__template = template
        self.__variables = self.__process_substitutions(variables)

    def __call__(self, **substitutions: Any) -> str:
        """
        Format the stored template using suitable substitutions.

        Args:
            substitutions (Optional[SDict[Any]], optional): Values that
                must be or are desired to be substituted into `self.template`.
                Defaults to None.

        Raises:
            ValueError: If `substitutions` contains keys not found in
                `self.variables`.
            ValueError: If `substitutions` does not contain required keys
                (i.e., keys in `self.variables` whose value is `None`).

        Returns:
            str: Formatted template.
        """

        substitutions = {**self.__variables, **self.__process_substitutions(substitutions)}
        omitted = {k for k, v in substitutions.items() if k in self.__variables and v is None}
        if len(omitted) > 0:
            raise ValueError(f"Values of keys {omitted} in `substitutions` must not be None")
        return self.__template.format(**substitutions)

    def __process_substitutions(self, sub: Optional[SDict[Any]]) -> SDict[Optional[str]]:
        return {} if sub is None else {k: None if v is None else str(v) for k, v in sub.items()}

    @property
    def template(self) -> str:
        return self.__template

    @property
    def variables(self) -> SDict[Optional[str]]:
        return self.__variables


class JSONInvalidError(ValueError):
    pass


class JsonParser(object):
    __TEMPLATE = """<context>
I used `json.loads()` in Python to parse the JSON string <<inputs.invalid-json-string>>, but it failed with error message <<inputs.error-message>>.
The JSON string is invalid and needs to be fixed.
</context>

<objective>
Fix the invalid JSON string.
You may need to fix quotes, brackets, commas, and escaping.
You **MUST** preserve all content and maintain the original structure (i.e., same hierarchy and nesting).
Do **NOT** modify or omit any original data (including data types).
</objective>

<style>
JSON
</style>

<tone>
Strict, properly formatted, correct
</tone>

<audience>
A computer program that can parse JSON string.
</audience>

<response>
Corrected JSON string, without preamble or postamble.
Do **NOT** include any additional commentary or Markdown formatting.
</response>

<inputs>
<invalid-json-string>
{string}
</invalid-json-string>

<error-message>
{error}
</error-message>
</inputs>"""

    def __init__(self, llm: Optional[Llm | list[Llm]] = None) -> None:
        if llm is None:
            self.__llm = []
        else:
            self.__llm = [llm] if isinstance(llm, Llm) else llm
        self.__get_prompt = TemplateFormatter(self.__TEMPLATE, string=None, error=None)

    def __call__(self, text: Optional[str], only_object: bool = True, **kwargs: Any) -> Optional[JsonObject]:
        if text is None:
            return None
        extracted = self.extract(text, only_object=only_object)
        if extracted is None:
            raise JSONInvalidError(f"`text` contains no valid JSON content, could be incomplete\n|\nv\n{text}")
        try:
            return json.loads(extracted)
        except JSONDecodeError as e:  # complete but invalid content
            chat_id = kwargs.get("chat_id", None)
            tsprint(
                colored_error(),
                f"{f'<{chat_id}> ' if chat_id is not None else ''}Repairing JSON:",
                format_error(e)[0],
                f"\n|\nv\n{extracted}",
                end="\n\n",
            )
            repaired = json_repair.loads(extracted, skip_json_loads=True)
            if len(repaired) > 0:
                return repaired
            prompt = self.__get_prompt(string=extracted, error=format_error(e)[0])
            for llm in self.__llm:  # try to fix JSON with LLM
                fixed, _ = llm(prompt, temperature=0.1)
                fixed = self.extract(fixed, only_object=only_object)
                if fixed is None:
                    continue
                try:
                    return json.loads(fixed)
                except JSONDecodeError:
                    repaired = json_repair.loads(fixed, skip_json_loads=True)
                    if len(repaired) > 0:
                        return repaired
                    continue
            raise

    @staticmethod
    def extract(text: Optional[str], only_object: bool = True) -> Optional[str]:
        if text is None:
            return None

        def get_pattern(only_object: bool) -> str:
            pattern = r"(\{.*\}"
            if not only_object:
                pattern += r"|\[.*\]|\".*?\"|-?\b\d+[\.\d+]*\b|\btrue\b|\bfalse\b|\bnull\b"
            pattern += ")"
            return pattern

        def is_object(text: str) -> bool:
            if text == "" or text[0] != "{":
                return False
            stack = ["}"]
            in_string, escape = False, False
            for i in range(1, len(text)):
                char = text[i]
                if in_string:
                    if escape:
                        escape = False  # escaped character
                    else:
                        if char == "\\":
                            escape = True  # next character will be escaped
                        elif char == '"':
                            in_string = False  # end of text
                else:
                    if char == '"':
                        in_string = True  # start of text
                        escape = False
                    else:
                        if char == "{":
                            stack.append("}")
                        elif char == "}":
                            if len(stack) == 0 or char != stack[-1]:
                                return False
                            stack.pop()
                            if len(stack) == 0:
                                return True  # valid closing of root structure
            return len(stack) == 0

        text = re.sub(
            r'("(?:\\.|[^"\\])*")|(\s*\/\/.*)',
            lambda matched: matched.group(1) if matched.group(1) is not None else "",
            text,
        )
        matched = re.search(get_pattern(only_object), text, flags=re.DOTALL)
        if matched is not None:
            extracted = matched.group(1)
            if only_object and not is_object(extracted):
                return None
            return extracted
        return None


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", type=str)
    parser.add_argument("--img", action="append", type=str, default=None)
    parser.add_argument("--model", type=str, required=True)
    parser.add_argument("-t", "--temperature", type=float, default=None)
    parser.add_argument("--base_url", type=str)
    parser.add_argument("--api_key", type=str)
    args = parser.parse_args()
    config = LlmConfig(model=args.model, base_url=args.base_url, api_key=args.api_key)
    llm = Llm(config)
    response, output = llm.chat(args.prompt, temperature=args.temperature, images=args.img)
    print(response)
    print(output.completion.usage.completion_tokens)


if __name__ == "__main__":
    main()
