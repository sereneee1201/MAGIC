# -*- coding: utf-8 -*-

import json

from magic.dataset.templates import ADJECTIVES_TEMPLATE, ROOM_TYPES_TEMPLATE
from magic.generation.modules import OUTPUT_GUIDANCE
from magic.utils.file import load_yaml
from magic.utils.llm import Llm, LlmConfig, TemplateFormatter
from magic.utils.misc import parse_cli_kwargs

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("mode", type=str, choices=("adjectives", "rooms"))
    parser.add_argument("-c", "--config", type=str, required=True, help="Path to a YAML configuration file.")
    parser.add_argument("--kwarg", action="append", type=str, default=None, help="Additional keyword argument.")
    args = parser.parse_args()
    config = load_yaml(args.config, replace_env_var=True)
    llm = Llm(LlmConfig(**config["llm"]["normal_llm"]), verbose=True)
    kwargs = parse_cli_kwargs(args.kwarg)

    match args.mode:
        case "adjectives":
            get_adjectives_prompt = TemplateFormatter(ADJECTIVES_TEMPLATE, output_guidance=OUTPUT_GUIDANCE)
            response, _ = llm.chat(get_adjectives_prompt(), temperature=0.2, to_json=True)
            adjectives = response["adjectives"]
            adjectives = sorted(set(map(lambda x: x.lower(), adjectives)))
            adjectives = json.dumps(adjectives, ensure_ascii=False)
            print(adjectives)
        case "rooms":
            buildings: str = kwargs["buildings"]
            get_room_types_prompt = TemplateFormatter(
                ROOM_TYPES_TEMPLATE, buildings=None, output_guidance=OUTPUT_GUIDANCE
            )
            response, _ = llm.chat(get_room_types_prompt(buildings=buildings), temperature=0.2, to_json=True)
            room_types = response["room_types"]
            room_types = sorted(set(map(lambda x: x.lower(), room_types)))
            room_types = {buildings: room_types}
            room_types = json.dumps(room_types, ensure_ascii=False)
            print(room_types)
