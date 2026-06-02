from typing import List
from openai import OpenAI
import json

from constants import *

def completion_with_backoff(client, **kwargs):
    return client.chat.completions.create(**kwargs)

def query(system_msg: List[dict], prompt: str, client, model) -> str:
    messages = system_msg
    messages.append({"role": "user", "content": prompt})
    try:
        chat_completion = completion_with_backoff(
            model=model,
            messages=messages,
            client=client
        )
        res = chat_completion.choices[0].message.content
        return res
    except Exception as e:
        print("GPT exception:", e)
        return ""
    
def sys_msg(sys_prompt, sample_inputs, sample_outputs):
    """Form system messages"""
    sys_msg = [{"role": "system", "content": sys_prompt}]
    for i in range(len(sample_inputs)):
        sys_msg.append({"role": "user", "content": sample_inputs[i]})
        sys_msg.append({"role": "assistant", "content": sample_outputs[i]})
    return sys_msg
    
def agent_planner(prompt: str, llm_bag):
    client = OpenAI(api_key=llm_bag["normal_llm"].api_key)
    planner_sys_msg = sys_msg(planner_sys_prompt, planner_sample_inputs, planner_sample_outputs)
    planner_res = query(planner_sys_msg, prompt, client, llm_bag["normal_llm"].model)
    return planner_res

def agent_validator(prompt: str, portal_count: dict, llm_bag):
    client = OpenAI(api_key=llm_bag["normal_llm"].api_key)
    val_prompt = {"prompt": prompt, "portal_count": portal_count}
    validator_sys_msg = [{"role": "system", "content": validator_sys_prompt}]
    validator_res = query(validator_sys_msg, json.dumps(val_prompt), client, llm_bag["normal_llm"].model)
    return validator_res