# -*- coding: utf-8 -*-

import json
import random
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from itertools import combinations
from os import makedirs
from typing import Optional

from tqdm import tqdm

from magic.dataset import DatapointConnection, DatapointPrompts, DatapointRoom, MagicDatapoint, MagicDatasetConfig
from magic.dataset.pools import *
from magic.dataset.templates import *
from magic.generation.modules import OUTPUT_GUIDANCE, OUTSIDE_DEF
from magic.utils.dtypes import SDict
from magic.utils.file import get_available_path, load_yaml
from magic.utils.llm import JsonParser, Llm, LlmConfig, LlmContent, TemplateFormatter
from magic.utils.maths import clamp
from magic.utils.misc import (
    colored_error,
    format_error,
    get_datetime,
    parse_cli_kwargs,
    remove_trailing_digits,
    tsprint,
)
from magic.utils.retry import auto_retry, set_max_retries

get_rooms_desc_prompt = TemplateFormatter(
    ROOMS_DESCRIPTION_TEMPLATE, buildings=None, rooms=None, output_guidance=OUTPUT_GUIDANCE, output_template=None
)
get_conn_desc_prompt = TemplateFormatter(
    CONNECTION_DESCRIPTION_TEMPLATE,
    buildings=None,
    room_1=None,
    room_2=None,
    description_1=None,
    description_2=None,
    connection=None,
    output_guidance=OUTPUT_GUIDANCE,
)
get_room_objects_prompt = TemplateFormatter(
    ROOM_OBJECTS_TEMPLATE, buildings=None, room=None, description=None, output_guidance=OUTPUT_GUIDANCE
)
get_room_objects_description_prompt = TemplateFormatter(
    ROOM_OBJECTS_DESCRIPTION_TEMPLATE,
    buildings=None,
    room=None,
    description=None,
    objects=None,
    output_guidance=OUTPUT_GUIDANCE,
)
get_room_objects_relations_prompt = TemplateFormatter(
    ROOM_OBJECTS_RELATIONS_TEMPLATE,
    buildings=None,
    room=None,
    description=None,
    objects=None,
    output_guidance=OUTPUT_GUIDANCE,
)
get_room_summary_prompt = TemplateFormatter(
    ROOM_SUMMARY_TEMPLATE,
    buildings=None,
    room=None,
    description=None,
    objects=None,
    object_relations=None,
    output_guidance=OUTPUT_GUIDANCE,
)
get_summary_template = TemplateFormatter(
    SUMMARY_TEMPLATE,
    buildings=None,
    n_rooms=None,
    rooms=None,
    connections=None,
    outside_def=OUTSIDE_DEF,
    output_guidance=OUTPUT_GUIDANCE,
)
get_humanized_prompt_template = TemplateFormatter(
    HUMANIZED_PROMPT_TEMPLATE, buildings=None, description=None, output_guidance=OUTPUT_GUIDANCE
)
get_sentence_prompt_template = TemplateFormatter(
    SENTENCE_PROMPT_TEMPLATE, buildings=None, description=None, output_guidance=OUTPUT_GUIDANCE
)


class MagicDatasetGenerator(object):
    def __init__(self, config: MagicDatasetConfig, llm_bag: SDict[LlmConfig]) -> None:
        self.__config = config
        json_parser = JsonParser(llm=Llm(llm_bag[config.llm], verbose=config.verbose))
        self.__llm = Llm(llm_bag[config.llm], json_parser=json_parser, verbose=config.verbose)

    def __call__(self, buildings: str) -> None:
        n_rooms = random.randint(1, 5) if self.config.n_rooms is None else self.config.n_rooms
        output_dir = self.config.parent_dir / buildings / str(n_rooms)
        makedirs(output_dir, exist_ok=True)
        log_path = get_available_path(output_dir / f"prompt_{buildings}_{n_rooms}_{get_datetime()}.json")
        open(log_path, "w", encoding="utf-8").close()
        dp = MagicDatapoint(buildings=buildings, config=self.config, log_path=log_path, n_rooms=n_rooms)
        dp.save()
        self.__get_rooms(dp)
        dp.save()
        dp.conversations["rooms_description"] = self.__get_rooms_description(dp)
        dp.save()
        # add special "__outside__" region for creating connections
        dp.rooms["__outside__"] = DatapointRoom(description=OUTSIDE_DEF)
        self.__create_connections(dp)
        dp.save()
        dp.conversations["connections_description"] = self.__get_connections_description(dp)
        # remove "__outside__" region from `data.rooms`
        dp.rooms.pop("__outside__")
        dp.save()
        dp.conversations["rooms_objects"] = self.__get_rooms_objects(dp)
        dp.save()
        dp.conversations["basic_summaries"] = self.__get_basic_summaries(dp)
        dp.save()

        summaries = [dp.summaries["overall"]]
        summaries.extend(f"{room.description} {room.summary}" for room in dp.rooms.values())
        if (conn_summary := dp.summaries["connections"]) is not None and conn_summary != "":
            summaries.append(conn_summary)
        dp.prompts = DatapointPrompts(full=" ".join(summaries))
        dp.save()

        dp.conversations["humanized_prompt"] = self.__get_humanized_prompt(dp)
        dp.save()
        dp.conversations["sentence_prompt"] = self.__get_sentence_prompt(dp)
        dp.save()

    def __get_rooms(self, dp: MagicDatapoint) -> None:
        chosen_types = {}
        for _ in range(dp.n_rooms):
            room_type = random.choice(BUILDINGS[dp.buildings])
            count = chosen_types.get(room_type, 0)
            chosen_types[room_type] = count = count + 1
            if count == 2:
                dp.rooms[f"{room_type} 1"] = dp.rooms.pop(room_type)
            room = f"{room_type}{f' {count}' if count > 1 else ''}"
            n_adj = random.randint(5, min(15, len(ADJECTIVES)))
            dp.rooms[room] = DatapointRoom(adjectives=random.sample(ADJECTIVES, k=n_adj))
        dp.rooms = dict(random.sample(list(dp.rooms.items()), k=len(dp.rooms)))  # induce randomness

    @auto_retry
    def __get_rooms_description(self, dp: MagicDatapoint) -> LlmContent:
        self.__llm.clear_messages()
        prompt = get_rooms_desc_prompt(
            buildings=dp.buildings,
            rooms=json.dumps({room_name: room.adjectives for room_name, room in dp.rooms.items()}, ensure_ascii=False),
            output_template=json.dumps({name: f"The {name} <FILL_IN>" for name in dp.rooms}, ensure_ascii=False),
        )
        response, llm_output = self.__llm.chat(prompt, temperature=self.config.temperature, to_json=True)
        if not isinstance(response, dict):
            raise RuntimeError()
        if len(response) != len(dp.rooms):
            raise RuntimeError()
        for room, des in response.items():
            if not isinstance(room, str):
                raise RuntimeError()
            if not isinstance(des, str):
                raise RuntimeError()
            dp.rooms[room].description = des
        self.__llm.clear_messages()
        return llm_output.content

    def __create_connections(self, dp: MagicDatapoint) -> None:
        # ensure a connected graph is formed with non-window connections
        remaining_rooms = list(dp.rooms.keys())
        connected_rooms = [remaining_rooms.pop(0)]
        while len(remaining_rooms) > 0:
            r1 = random.choice(connected_rooms)
            r2 = remaining_rooms.pop(0)
            conn_type = random.choice(TO_OUTSIDE if r1 == "__outside__" or r2 == "__outside__" else PATHWAYS)
            dp.connections.append(DatapointConnection(region_a=r1, region_b=r2, conn_type=conn_type))
            connected_rooms.append(r2)
        # create extra connections
        exist_conns = set(tuple(sorted((conn.region_a, conn.region_b))) for conn in dp.connections)
        for r1, r2 in combinations(dp.rooms.keys(), 2):
            if random.random() > 0.5:
                conn_type = random.choice(WINDOWS if tuple(sorted((r1, r2))) in exist_conns else CONNECTIONS)
                dp.connections.append(DatapointConnection(region_a=r1, region_b=r2, conn_type=conn_type))
        dp.connections = random.sample(dp.connections, k=len(dp.connections))  # induce randomness

    def __get_connections_description(self, dp: MagicDatapoint) -> list[Optional[LlmContent]]:
        @auto_retry
        def get_conn_desc(conn: DatapointConnection) -> tuple[Optional[str], Optional[LlmContent]]:
            if conn.conn_type != "open":
                _llm = deepcopy(self.__llm)
                prompt = get_conn_desc_prompt(
                    buildings=dp.buildings,
                    room_1=remove_trailing_digits(conn.region_a),
                    room_2=remove_trailing_digits(conn.region_b),
                    description_1=dp.rooms[conn.region_a].description,
                    description_2=dp.rooms[conn.region_b].description,
                    connection=conn.conn_type,
                )
                response, llm_output = _llm.chat(prompt, temperature=self.config.temperature, to_json=True)
                content = llm_output.content
                if not isinstance(response, dict):
                    raise RuntimeError()
                if "description" not in response:
                    raise RuntimeError()
                description = response["description"]
                if not isinstance(description, str):
                    raise RuntimeError()
            else:
                description, content = None, None
            return description, content

        conversations = []
        with ThreadPoolExecutor(max_workers=self.config.max_threads) as executor:
            for i, (des, convo) in enumerate(executor.map(get_conn_desc, dp.connections)):
                dp.connections[i].description = des
                conversations.append(convo)
        return conversations

    def __get_rooms_objects(self, dp: MagicDatapoint, drop: float = 0.2) -> list[list[LlmContent]]:
        @auto_retry
        def get_room_objects(name_and_detail: tuple[str, DatapointRoom]) -> tuple[list[str], LlmContent]:
            room_name, room = name_and_detail
            room_name = remove_trailing_digits(room_name)
            _llm = deepcopy(self.__llm)
            prompt = get_room_objects_prompt(buildings=dp.buildings, room=room_name, description=room.description)
            response, llm_output = _llm.chat(prompt, temperature=self.config.temperature, to_json=True)
            if not isinstance(response, dict):
                raise RuntimeError()
            objects = []
            for obj, n in response.items():
                if not isinstance(obj, str):
                    raise RuntimeError()
                if not isinstance(n, int):
                    raise RuntimeError()
                if n <= 0:
                    continue
                obj = obj.replace("_", " ")
                n = clamp(n, 1, self.config.max_n_per_object)  # set an upper limit for the number of objects
                n = random.randint(0, n) if random.random() > (1 - drop) else n  # induce randomness
                if n == 0:
                    continue
                elif n == 1:
                    objects.append(obj)
                elif n > 1:
                    objects.extend([f"{obj} {i + 1}" for i in range(n)])
            return objects, llm_output.content

        @auto_retry
        def get_room_objects_description(name_and_detail: tuple[str, DatapointRoom]) -> tuple[SDict[str], LlmContent]:
            room_name, room = name_and_detail
            room_name = remove_trailing_digits(room_name)
            _llm = deepcopy(self.__llm)
            prompt = get_room_objects_description_prompt(
                buildings=dp.buildings,
                room=room_name,
                description=room.description,
                objects=json.dumps(room.objects_list, ensure_ascii=False),
            )
            response, llm_output = _llm.chat(prompt, temperature=self.config.temperature, to_json=True)
            if not isinstance(response, dict):
                raise RuntimeError()
            if len(response) != len(room.objects_list):
                raise RuntimeError()
            if len(set(response.keys()).difference(set(room.objects_list))) > 0:
                raise RuntimeError()
            for obj, des in response.items():
                if not isinstance(obj, str):
                    raise RuntimeError()
                if not isinstance(des, str):
                    raise RuntimeError()
            return response, llm_output.content

        @auto_retry
        def get_room_objects_relations(
            name_and_detail: tuple[str, DatapointRoom],
        ) -> tuple[list[list[str] | str], LlmContent]:
            room_name, room = name_and_detail
            room_name = remove_trailing_digits(room_name)
            _llm = deepcopy(self.__llm)
            prompt = get_room_objects_relations_prompt(
                buildings=dp.buildings,
                room=room_name,
                description=room.description,
                objects=json.dumps(room.objects_desc, ensure_ascii=False),
            )
            response, llm_output = _llm.chat(prompt, temperature=self.config.temperature, to_json=True)
            if not isinstance(response, dict):
                raise RuntimeError()
            if "relations" not in response:
                raise RuntimeError()
            relations = response["relations"]
            if not isinstance(relations, list):
                raise RuntimeError()
            object_relations = []
            for rel in relations:
                if not isinstance(rel, list):
                    raise RuntimeError()
                if len(rel) != 3:
                    raise RuntimeError()
                if not all(isinstance(item, str) for item in rel):
                    raise RuntimeError()
                if rel[0] not in room.objects_desc:
                    continue
                if rel[1].strip() == "":
                    continue
                if rel[2] not in room.objects_desc:
                    continue
                object_relations.append((rel[0], rel[1].strip(), rel[2]))
            return object_relations, llm_output.content

        @auto_retry
        def get_room_summary(name_and_detail: tuple[str, DatapointRoom]) -> tuple[str, LlmContent]:
            room_name, room = name_and_detail
            room_name = remove_trailing_digits(room_name)
            _llm = deepcopy(self.__llm)
            prompt = get_room_summary_prompt(
                buildings=dp.buildings,
                room=room_name,
                description=room.description,
                objects=json.dumps(room.objects_desc, ensure_ascii=False),
                object_relations=json.dumps(room.object_relations, ensure_ascii=False),
            )
            response, llm_output = _llm.chat(prompt, temperature=self.config.temperature, to_json=True)
            if not isinstance(response, dict):
                raise RuntimeError()
            if "summary" not in response:
                raise RuntimeError()
            summary = response["summary"]
            if not isinstance(summary, str):
                raise RuntimeError()
            return summary, llm_output.content

        conversations = {}
        room_names = list(dp.rooms.keys())
        with ThreadPoolExecutor(max_workers=self.config.max_threads) as executor:
            conversations["room_objects"] = []
            for i, (lst, convo) in enumerate(executor.map(get_room_objects, dp.rooms.items())):
                dp.rooms[room_names[i]].objects_list = lst
                conversations["room_objects"].append(convo)
        dp.save()
        with ThreadPoolExecutor(max_workers=self.config.max_threads) as executor:
            conversations["room_objects_description"] = []
            for i, (desc, convo) in enumerate(executor.map(get_room_objects_description, dp.rooms.items())):
                dp.rooms[room_names[i]].objects_desc = desc
                conversations["room_objects_description"].append(convo)
        dp.save()
        with ThreadPoolExecutor(max_workers=self.config.max_threads) as executor:
            conversations["room_objects_relations"] = []
            for i, (relations, convo) in enumerate(executor.map(get_room_objects_relations, dp.rooms.items())):
                dp.rooms[room_names[i]].object_relations = relations
                conversations["room_objects_relations"].append(convo)
        dp.save()
        with ThreadPoolExecutor(max_workers=self.config.max_threads) as executor:
            conversations["room_summary"] = []
            for i, (summary, convo) in enumerate(executor.map(get_room_summary, dp.rooms.items())):
                dp.rooms[room_names[i]].summary = summary
                conversations["room_summary"].append(convo)
        dp.save()
        return conversations

    @auto_retry
    def __get_basic_summaries(self, dp: MagicDatapoint) -> LlmContent:
        self.__llm.clear_messages()
        rooms = {room_name: f"{room.description} {room.summary}" for room_name, room in dp.rooms.items()}
        prompt = get_summary_template(
            buildings=dp.buildings,
            n_rooms=dp.n_rooms,
            rooms=json.dumps(rooms, ensure_ascii=False),
            connections=json.dumps([conn.model_dump() for conn in dp.connections], ensure_ascii=False),
        )
        response, llm_output = self.__llm.chat(prompt, temperature=self.config.temperature, to_json=True)
        if not isinstance(response, dict):
            raise RuntimeError()
        if "overall_summary" not in response:
            raise RuntimeError()
        overall_summary = response["overall_summary"]
        if not isinstance(overall_summary, str):
            raise RuntimeError()
        if "connections_summary" not in response:
            raise RuntimeError()
        connections_summary = response["connections_summary"]
        if not isinstance(connections_summary, str):
            raise RuntimeError()
        dp.summaries = {"overall": overall_summary, "connections": connections_summary}
        self.__llm.clear_messages()
        return llm_output.content

    @auto_retry
    def __get_humanized_prompt(self, dp: MagicDatapoint) -> LlmContent:
        self.__llm.clear_messages()
        prompt = get_humanized_prompt_template(buildings=dp.buildings, description=dp.prompts.full)
        response, llm_output = self.__llm.chat(prompt, temperature=self.config.temperature, to_json=True)
        if not isinstance(response, dict):
            raise RuntimeError()
        if "speech" not in response:
            raise RuntimeError()
        humanized = response["speech"]
        if not isinstance(humanized, str):
            raise RuntimeError()
        dp.prompts.humanized = humanized
        dp.prompts.pct_change_humanized = len(humanized.split()) / len(dp.prompts.full.split()) - 1.0
        self.__llm.clear_messages()
        return llm_output.content

    @auto_retry
    def __get_sentence_prompt(self, dp: MagicDatapoint) -> LlmContent:
        self.__llm.clear_messages()
        prompt = get_sentence_prompt_template(buildings=dp.buildings, description=dp.prompts.full)
        response, llm_output = self.__llm.chat(prompt, temperature=self.config.temperature, to_json=True)
        if not isinstance(response, dict):
            raise RuntimeError()
        if "sentence" not in response:
            raise RuntimeError()
        sentence = response["sentence"]
        if not isinstance(sentence, str):
            raise RuntimeError()
        dp.prompts.sentence = sentence
        dp.prompts.pct_change_sentence = len(sentence.split()) / len(dp.prompts.full.split()) - 1.0
        self.__llm.clear_messages()
        return llm_output.content

    @property
    def config(self) -> MagicDatasetConfig:
        return self.__config


def _cli() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("buildings", type=str, help="Type of building (plural; e.g., apartments).")
    parser.add_argument("-c", "--config", type=str, required=True, help="Path to a YAML configuration file.")
    parser.add_argument("--kwarg", action="append", type=str, default=None, help="Additional keyword argument.")
    args = parser.parse_args()
    args.buildings = args.buildings.lower()
    config = load_yaml(args.config, replace_env_var=True)
    dp_config = MagicDatasetConfig(**{**config.get("dataset", {}), **parse_cli_kwargs(args.kwarg)})
    set_max_retries(dp_config.max_retries)
    llm_bag = {str(k): LlmConfig(**v) for k, v in config["llm"].items()}
    tsprint(f"Configuration: {dp_config.model_dump()}\n")

    dp_gen = MagicDatasetGenerator(dp_config, llm_bag)
    for idx in tqdm(range(dp_config.n_prompts), desc="Datapoints"):
        try:
            dp_gen(args.buildings)
        except KeyboardInterrupt:
            return
        except BaseException as e:
            err = "\n|\nv\n".join(format_error(e))
            tsprint(colored_error(), f"Exception(s) in {idx + 1}: {err}\n\n")
            continue


if __name__ == "__main__":
    _cli()
