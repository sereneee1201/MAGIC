# -*- coding: utf-8 -*-

ADJECTIVES_TEMPLATE = """## Task description

Generate a complete list of unique adjectives to describe rooms.
Avoid synonyms or variations of previously used words.
Do not generate non-sense.

## Output format

{output_guidance}

{{"adjectives": ["<FILL_IN>", ...]}}"""

ROOM_TYPES_TEMPLATE = """## Task description

Generate a complete list of room types that can be found in {buildings}.
Make sure no room types are repeated or similar.

## Output format

{output_guidance}

{{"room_types": ["<FILL_IN>", ...]}}"""

ROOMS_DESCRIPTION_TEMPLATE = """## Task description

You are a professional interior designer who excels at interior design of {buildings}.
You are given some room types that can be found in {buildings}.
These room types will be used to construct corresponding rooms in a one-storey building.
Each room is associated with some adjectives: _{{rooms}}_
Now, for each room, generate a short and concise description of the room's shape as well as the colors and materials of its floor and wall in your own words using the given adjectives (and the given room name).

## Guidance

- It is not a must to use the exact wordings of the given adjectives.
- For each room, if some adjectives are contradicting one another, randomly pick only one of them to use.

## Known information

_{{rooms}}_: {rooms}

## Output format

{output_guidance}

{output_template}"""

CONNECTION_DESCRIPTION_TEMPLATE = """## Task description

You are a professional interior designer who excels at interior design of {buildings}.
You are designing one that contains (1) "{room_1}" and (2) "{room_2}".
(1) "{room_1}" has the following description: _{{description1}}_
(2) "{room_2}" has the following description: _{{description2}}_
These two rooms are connected with a {connection}.
Using your imagination, generate a concise description of the {connection}'s appearance (color, material, attributes; "attributes" refers to comma-separated descriptive phrases that are solely about the object's appearance and are independent of other objects).
A description **MUST** be able to resemble the following sentence: "A/An `color` <<OBJECT_NAME>> made with `material` that is `attributes`."

## Known information

_{{description1}}_: {description_1}

_{{description2}}_: {description_2}

## Output format

{output_guidance}

{{"description": "<<FILL_IN>>"}}"""

ROOM_OBJECTS_TEMPLATE = """## Task description

You are a professional interior designer who excels at interior design of {buildings}.
Particularly, you are working on a {room} with the following description: _{{description}}_
Now, generate the objects (each with its quantity) that should exist in this room.

## Guidance

- Besides generating objects that can be found in a typical {room}, unleash your imagination and generate objects that are likely to be associated with the given description.
- You **MUST** generate at least one lighting unit (i.e., an object made for illumination).
- Do **NOT** generate door, doorframe, window, or stair.
- Do **NOT** use plural form, even if the quantity of that object is more than one.
- Do **NOT** use underscore in object name.
- Make sure the quantity is an integer greater than 0.
- Refrain from repeatedly generating identical or similar objects.

## Known information

_{{description}}_: {description}

## Output format

{output_guidance}

{{"<<FILL_IN_OBJECT>>": <<FILL_IN_QUANTITY>>}}"""

ROOM_OBJECTS_DESCRIPTION_TEMPLATE = """## Task description

You are a professional interior designer who excels at interior design of {buildings}.
Particularly, you are working on a {room} with the following description: _{{description}}_
This room contains the following objects: _{{objects}}_
Now, for each object, generate a concise description about the object's appearance (color, material, attributes; "attributes" refers to comma-separated descriptive phrases that are solely about the object's appearance and are independent of other objects).
A description **MUST** be able to resemble the following sentence: "A/An `color` <<OBJECT_NAME>> made with `material` that is `attributes`."

## Guidance

- **All** objects **MUST** be used.
- If you expect several objects to be identical, their descriptions **MUST** also be identical.
- In the description, do **NOT** mention other objects. Also, do **NOT** include the object's position relative to other objects.

## Known information

_{{description}}_: {description}

_{{objects}}_: {objects}

## Output format

{output_guidance}

You **MUST** include **all** provided object names **as is**.

{{"<<USE_PROVIDED_OBJECT_NAME>>": "<<FILL_IN_DESCRIPTION>>", ...}}"""

ROOM_OBJECTS_RELATIONS_TEMPLATE = """## Task description

You are a professional interior designer who excels at interior design of {buildings}.
Particularly, you are working on a {room} with the following description: _{{description}}_
This room contains the following objects (each coupled with a description): _{{objects}}_
Now, be as creative as you can (but remain realistic and practical) and generate sufficient 3-tuples of [objectA, relation, objectB] (which encode different relations between pairs of objects).
`objectA` and `objectB` are object names; `relation` is a phrase or an incomplete sentence (numerical values can be optionally included, such as a desired distance (meter) between two objects) that describes how `objectA` is physically related to `objectB` according to `relation`.
In other words, a 3-tuple should be able to resemble the following sentence: "`objectA` is `relation` `objectB`."
For example, if a coffee cup is placed on top of a table, you could generate `["coffee cup", "on", "table"]`.

## Guidance

- **All** objects **MUST** be used at least once.

## Known information

_{{description}}_: {description}

_{{objects}}_: {objects}

## Output format

{output_guidance}

You **MUST** use **all** provided object names **as is**.

{{
  "relations": [
    ["<<USE_PROVIDED_OBJECT_NAME>>", "<<FILL_IN_RELATION>>", "<<USE_PROVIDED_OBJECT_NAME>>"],
    ...
  ]
}}"""

ROOM_SUMMARY_TEMPLATE = """## Task description

You are a professional interior designer who excels at interior design of {buildings}.
Particularly, you are working on a {room} with the following description: _{{description}}_
This room contains the following objects (each coupled with a description): _{{objects}}_
These objects are related to one another: _{{object-relations}}_
Now, using _{{objects}}_ and _{{object-relations}}_, generate a **one-paragraph** summary regarding the objects in this room as well as where they are exactly placed and how they are exactly related.
You **MUST** keep every object's description.

## Guidance

- **All** given objects must be used, but you can use them in any order you want.
- If there is a collection of similar/identical objects, you **MUST explicitly** mention the **number** of objects (e.g., "five books" instead of "a collection of books").
- Each element in _{{object-relations}}_ is a 3-tuple [objectA, relation, objectB] which encodes a relation between a pair of objects.
`objectA` and `objectB` are object names; `relation` is a phrase or an incomplete sentence (numerical values can be optionally included) that describes how `objectA` is physically related to `objectB` according to `relation`.
- You may use "looking from ..." to describe the room from a specific perspective, making the summary more vivid.

## Known information

_{{description}}_: {description}

_{{objects}}_: {objects}

_{{object-relations}}_: {object_relations}

## Output format

{output_guidance}

{{"summary": "In this room, <<FILL_IN>>"}}"""

SUMMARY_TEMPLATE = """## Task description

You are a professional interior designer who excels at interior design of {buildings}.
You are designing one with {n_rooms} room(s) (each has its own summary): _{{rooms}}_
Some of these rooms are connected (with or without a door): _{{connections}}_
Now, generate two concise summaries in your own words.
The first one is a one-sentence overall description of the building's configuration (floor plan).
The second one consists of all connections in this building (i.e., all pairs of rooms that are connected, how they are connected, and the appearance of connection objects).

## Guidance

- In _{{connections}}_, region "__outside__" refers to {outside_def}.
- A connection type of "open" refers to the absence of a shared boundary between two rooms.

## Known information

_{{rooms}}_: {rooms}

_{{connections}}_: {connections}

## Output format

{output_guidance}

{{"overall_summary": "<<FILL_IN>>", "connections_summary": "<<FILL_IN>>"}}"""

HUMANIZED_PROMPT_TEMPLATE = """## Task description

You are a professional real estate agent who excels at introducing any type of real estate to your clients.
You are given a very comprehensive description of one of the latest {buildings} in your area: _{{description}}_
Now, rewrite the description into a one-paragraph natural speech (starting with "A"/"An") that is easy to understand and appealing to your clients.

## Guidance

- You **MUST** use all provided information from the description in your prompt.

## Known information

_{{description}}_: {description}

## Output format

{output_guidance}

{{"speech": "A/An <<FILL_IN>>"}}"""

SENTENCE_PROMPT_TEMPLATE = """## Task description

You are a professional real estate agent who excels at introducing any type of real estate to your clients.
You are given a very comprehensive description of one of the latest {buildings} in your area: _{{description}}_
Now, summarize the description into one concise sentence (starting with "A"/"An").

## Known information

_{{description}}_: {description}

## Output format

{output_guidance}

{{"sentence": "A/An <<FILL_IN>>"}}"""
