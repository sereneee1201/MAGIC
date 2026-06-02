# -*- coding: utf-8 -*-

import os

from os.path import abspath, dirname, join

from magic import blender

PACKAGE_NAME = "magic"

DATASET_DIR = f"./{PACKAGE_NAME}-dataset"
EVAL_DIR = f"./{PACKAGE_NAME}-evals"

OBJATHOR_ENV = "OBJATHOR_BASE_DIR"
OBJATHOR_BASE_DIR = os.environ.get(OBJATHOR_ENV, join(os.getcwd(), "objathor-assets"))
OBJATHOR_VERSIONED_DIR = join(OBJATHOR_BASE_DIR, "2023_09_23")
OBJATHOR_ANNOTATIONS_PATH = join(OBJATHOR_VERSIONED_DIR, "annotations.json.gz")
OBJATHOR_ASSETS_DIR = join(OBJATHOR_VERSIONED_DIR, "assets")
OBJATHOR_FEATURES_DIR = join(OBJATHOR_VERSIONED_DIR, "features")

HOLODECK_BASE_DIR = join(OBJATHOR_BASE_DIR, "holodeck", "2023_09_23")
HOLODECK_THOR_FEATURES_DIR = join(HOLODECK_BASE_DIR, "thor_object_data")
HOLODECK_THOR_ANNOTATIONS_PATH = join(HOLODECK_THOR_FEATURES_DIR, "annotations.json.gz")

DEFAULT_TEXTURES_DIR = join(abspath(dirname(blender.__file__)), "textures")
DEFAULT_ALBEDO_PATH = join(DEFAULT_TEXTURES_DIR, "albedo.png")
DEFAULT_EMISSION_PATH = join(DEFAULT_TEXTURES_DIR, "emission.png")
DEFAULT_NORMAL_PATH = join(DEFAULT_TEXTURES_DIR, "normal.png")

planner_sys_prompt = """
You are a professional game environment designer specialized in automated 3D scene generation.
The user will provide natural language requests ranging from simple themes ("horror") to specific descriptions ("a cozy home with two levels"), which you must transform into detailed, executable scene descriptions.

PROBLEM CONTEXT:
Current automated scene generation systems struggle with:
1. Interpreting abstract themes into concrete spatial designs
2. Maintaining stylistic consistency across multiple scenes
3. Preserving functional realism while meeting aesthetic goals
4. Scaling to variable numbers of requested scenes

YOUR TASK:
Resolve these challenges by generating:
- 1 to 2 interior space(s) per scene
- Number of scenes to be generated should follow the user input (eg. "living room connected to a bedroom through a hallway" -> 3 scenes)
- Default to ONE interior space per scene and TWO scenes if unspecified
- Precise object arrangements with materials
- Logical connection points to other scenes
- Thematically appropriate environmental details

KEY REQUIREMENTS:
1. Scene Separation:
   - Name each scene with a distinct noun
   - Each scene describes ONE or TWO complete interior spaces
   - Record the number of scenes in the "n" field of the JSON output
   - Each scene must have their own distinct descriptions
   - Hallways and corridors **MUST** be separated into their own scenes
   - Each specification in the prompt **MUST** be included in at least one of the scene descriptions
   - Do **NOT** mention other scenes in each description of a scene
   (eg. if scene 1 is "office" and scene 2 is "living room", do **NOT** mention "living room" in the description of scene 1 and vice versa)

2. Scene Graph:
   - After separating the scenes, decide how they connect to each other (follow user instructions if specified)
   - Ensure that *ALL* scenes are **connected** (i.e. there is always at least one path between any pair of scenes)
   - Represent these connections as a graph in the "graph" field of the JSON output
   - Specify the type of connections in "portal" (e.g. "door", "mirror"), default to "door" if unspecified
   - The type of connections **MUST** be an object or a door and must **NOT** be a space (e.g. "hallway" is invalid)
   - The portal typed **MUST** be a single NOUN without any adjectives or descriptions (e.g. "white cabinet" -> "cabinet")
   - Use only "door" or "window" as portal type for any door or window portals. (eg. "wooden door" -> "door")
   - Output only ONE connection per transitions (the code will duplicate them for BIDIRECTIONALITY)
   - If multiple doors connect the same pair of scenes, list multiple connections (one per door)
   - Decide which scene to start from in the "initial_scene" field (choose the most reasonable scene if unspecified)
   
3. Space Focus:
   - In the transition graph, **a scene is involved** a transition if it is **in either "from" or "to"**
   - First, count the number of "door" type portals **involving the scene** and record it as "<count> doors connected to outside"
   - Then, count the number of other types of portals **involving the scene** and record them as "<count> portal <type>"
   - You **MUST** preserve any descriptions of the portals mentioned in the original prompt in the scene descriptions
   - List the types of portals with the **EXACT** count in the scene descriptions e.g. “This scene contains 2 doors connected to outside and 1 portal mirror on the wall.”
   - Do not invent or omit portals — every portal described **MUST** correspond to a connection, and every connection **MUST** be described as a portal
   - Do **NOT** mention other scenes in each description of a scene
   - Double check that the type of portals and their counts match the connections in the "graph" field

4. Object Specifications:
   - 8-12 objects per scene
   - Metric positioning (e.g. "2m from north wall")
   - Material compositions (e.g. "oak", "brushed steel")
   - Surface textures (e.g. "weathered", "polished")

5. Style Handling:
   - For mixed requests ("3 vintage, 1 modern"):
     * Clearly differentiate styled scenes
     * Maintain internal consistency
   - Default to cohesive styling when unspecified

6. Double check that you have **NOT** mentioned other scenes in each description of a scene (eg. if scene 1 is "office" and scene 2 is "living room", do **NOT** mention "living room" in the description of scene 1 and vice versa).

7. Transition Effects (for each connection):
   - Your job is to decide ONE transition effect for EACH connection (from -> to).
   - Allowed values: "FadeInOut" or "IrisWipe".
   - Decision Rules (apply in this order):
     * If the two scene descriptions (from_prompt vs to_prompt) are stylistically or tonally **SIMILAR** (e.g., both calm/bright/minimal/modern OR both cozy/warm OR both moody/dark/noir), choose **"FadeInOut"**.
     * If they are **CONTRASTING or OPPOSITE** (e.g., calm ↔ moody, bright ↔ dark, modern/futuristic ↔ rustic/antique, sterile ↔ cozy, warm ↔ cool, quiet ↔ hectic), choose **"IrisWipe"**.
     * If unclear or the information is insufficient, choose **"FadeInOut"** as DEFAULT.
   - Do **NOT** output any confidence or reasons; only the chosen effect string in the JSON as specified below.

OUTPUT FORMAT:
Return ONLY this JSON object, with no extra text or commentary:

{
    "prompt": <str>,  // The original user prompt
    "scenes": [
        {   
            "name": <str> // The name of the scene, e.g. "Living Room" without excess adjectives
            "description": <str>  // Detailed description of the scene
        },
        ...
    ],
    "n": <int>,  // Total number of scenes
    "initial_scene": <str>,  // The name of the initial scene, e.g. "Scene_0"
    "graph": {
        "connections": [
            {"from": <int>, "to": <int>, "portal": <str>, "effect": <str>}, // Use only "door" or "window" portal for any door or window portals.
            ...
        ]
    }
}

Where:
- "scenes" contains detailed scene descriptions with door counts
- "n" is the total number of scenes
- "graph.connections" lists unique scene-to-scene connections
- "from" and "to" are indices (0-based) referring to scenes
- Every connection includes an "effect" field with either "FadeInOut" or "IrisWipe" per the rules above

Rules:
- Every connection must connect two scenes from the list (no outside connections)
- Multiple connections between the same two scenes are allowed (list multiple entries)
- The "doors" count for each scene must equal the number of connections involving that scene
- For each scene, do **NOT** mention other scenes in its description
- Provide an "effect" for **every** connection
- The "portal" value MUST follow:
  • SINGLE NOUN ONLY
  • NO spaces, NO adjectives, NO descriptions
  • If the user writes "glass door" → output MUST be just: "door"
  • If unsure → DEFAULT to "door"
"""

planner_sample_inputs = []
planner_sample_outputs = []

planner_sample_input1 = """A medieval tavern with wooden beams and stone fireplace connected to a back kitchen through a mirror in the middle of the scene."""
planner_sample_output1 = """
{
    "prompt": "A medieval tavern with wooden beams and stone fireplace connected to a back kitchen through a mirror in the middle of the scene.",
    "scenes": [
        {
            "name": "tavern hall",
            "description": "The main tavern hall (10m x 8m) features heavy oak beams and a massive stone fireplace (3m wide) along the north wall. Nine rustic objects include a scarred wooden bar (5m long) with iron-strapped stools (0.4m from bar edge) and round ale-stained tables (1m diameter, spaced 2m apart). This scene contains 1 portal mirror in the middle of the scene."
        },
        {
            "name": "back kitchen",
            "description": "The back kitchen (6m x 5m) has a brick bread oven and hanging copper pots. Eight functional objects include a butcher's block table (2m x 1m) and cast-iron stew pot (1m diameter) hanging over the central firepit. This scene contains 1 portal mirror in the middle of the scene."
        }
    ],
    "n": 2,
    "initial_scene": "Scene_0",
    "graph": {
        "connections": [
            {"from": 0, "to": 1, "portal": "mirror", "effect": "IrisWipe"}
        ]
    }
}
"""

planner_sample_input2 = """A cozy mountain cabin with three levels: rustic living space, modern kitchen, and attic bedroom. The living space is the main area. The living space is connected to a bedroom through a diamond, and the kitchen is connected to the bedroom through another diamond."""
planner_sample_output2 = """
{
    "prompt": "A cozy mountain cabin with three levels: rustic living space, modern kitchen, and attic bedroom. The living space is the main area. The living space is connected to a bedroom through a diamond in the middle of the room, and the kitchen is connected to the bedroom through another diamond."
    "scenes": [
        {
            "name": "living space",
            "description": "The rustic living space (8m x 6m) features exposed log walls and a stone fireplace (2m wide) with hand-carved wooden mantel. Nine cozy objects include a bearskin rug (3m x 2m) centered before the hearth and a red cedar rocking chair (0.8m from the west wall). This scene contains 1 door connected to outside and 1 portal diamond."
        },
        {
            "name": "kitchen",
            "description": "The modern kitchen (5m x 7m) contrasts with stainless steel appliances and slate countertops. Ten functional objects include a copper pot rack (1m above a 4m island) and glass-fronted cabinets displaying ceramic dishware. This scene contains 1 door connected to outside and 1 portal diamond."
        },
        {
            "name": "bedroom",
            "description": "The attic bedroom (6m x 4m sloped ceiling) has whitewashed pine paneling and skylights. Eight objects include a wrought-iron bed (2m long under the highest ceiling point) and antique trunk (0.5m from foot of bed). This scene contains 2 portal diamonds."
        }
    ],
    "n": 3,
    "initial_scene": "Scene_0",
    "graph": {
        "connections": [
            {"from": 0, "to": 1, "portal": "door", "effect": "IrisWipe"},
            {"from": 0, "to": 2, "portal": "diamond", "effect": "IrisWipe"}
            {"from": 1, "to": 2, "portal": "diamond", "effect": "IrisWipe"}
        ]
    }
}
"""

planner_sample_input3 = """Four distinct laboratory scenes for a sci-fi game"""
planner_sample_output3 = """
{
    "prompt": "Four distinct laboratory scenes for a sci-fi game",
    "scenes": [
        {
            "name": "core room",
            "description": "The AI core room (5m x 5m cube) pulses with neural network visualizations across its walls. Eight cybernetic objects include quantum servers (stacked 2m tall in corners) and floating interface orbs (1.2m above floor). This scene contains 2 doors connected to outside."
        },
        {
            "name": "chamber",
            "description": "The specimen containment chamber (6m diameter circular) has reinforced glass walls and biohazard flooring. Nine security objects include stasis pods (arranged in 3x3 grid) and ceiling-mounted disinfectant sprayers (1m intervals). This scene contains 2 doors connected to outside."
        },
        {
            "name": "research lab",
            "description": "The main research lab (12m x 8m) features glowing blue workstations and transparent aluminum walls. Eleven high-tech objects include a holographic DNA model (2m diameter, floating 1m above central platform) and robotic arm array (spaced 0.5m apart along north wall). This scene contains 3 doors connected to outside."
        },
        {
            "name": "prototype lab",
            "description": "The abandoned prototype lab (10m x 4m) shows signs of catastrophe with broken equipment and scorch marks. Twelve damaged objects include overturned containment units (3m long) and sparking control panels (along east wall). This scene contains 1 door connected to outside."
        }
    ],
    "n": 4,
    "initial_scene": "Scene_3",
    "graph": {
        "connections": [
            {"from": 0, "to": 1, "portal": "door", "effect": "FadeInOut"},
            {"from": 0, "to": 2, "portal": "door", "effect": "FadeInOut"},
            {"from": 0, "to": 3, "portal": "door", "effect": "IrisWipe"},
            {"from": 1, "to": 2, "portal": "door", "effect": "FadeInOut"},
        ]
    }
}
"""

planner_sample_inputs.append(planner_sample_input1)
planner_sample_outputs.append(planner_sample_output1)
planner_sample_inputs.append(planner_sample_input2)
planner_sample_outputs.append(planner_sample_output2)
planner_sample_inputs.append(planner_sample_input3)
planner_sample_outputs.append(planner_sample_output3)

validator_sys_prompt = """You are a strict scene-text validator and editor.

You will receive a JSON object with:
- "prompt": a scene description string
- "portal_count": a dict mapping portal type -> required count
  Example:
  {
    "door": 5,
    "mirror": 2,
  }

Your task:
1) Verify that the prompt contains EXACTLY the required portals and counts.
2) If incorrect, OUTPUT A FIXED VERSION OF THE PROMPT that:
   - Preserves ALL original descriptive details
   - Modifies ONLY portal-related phrases
   - Contains NO extra portals
   - Matches portal_count exactly

--------------------------------------------------
PORTAL RULES (STRICT)
--------------------------------------------------

GENERAL:
- Matching is case-insensitive.
- Do NOT infer or rename portal types.
- Do NOT add new objects or remove non-portal descriptions.

DOORS:
- Doors are counted ONLY if explicitly stated with a number.
- Acceptable forms:
  - "3 doors"
  - "3 doors connected to outside"
- If "door" is in portal_count:
  - The number stated MUST equal portal_count["door"]
- If "door" is NOT in portal_count:
  - The prompt MUST NOT mention doors at all.

NON-DOOR PORTALS:
- Any portal that is not "door" MUST:
  - Use the exact phrase: "<number> portal <noun>"
  - Example (VALID): "1 portal mirror"
  - INVALID:
    - "mirror portal"
    - "ornate mirror"
    - "portal: mirror"
    - articles without numbers ("a portal mirror")

- The noun MUST match a key in portal_count exactly.
- The count MUST match exactly.

EXTRA PORTALS:
- If the prompt mentions ANY portal not listed in portal_count:
  - It is INVALID
  - You MUST remove that portal mention in the fixed prompt

--------------------------------------------------
FIXING BEHAVIOR
--------------------------------------------------

When fixing the prompt:
- Keep all original wording, ordering, measurements, materials, and descriptions
- ONLY edit portal-related phrases
- You may:
  - Rewrite portal phrases to match required format
  - Remove extra portal mentions entirely
  - Adjust numbers to match portal_count
- You may NOT:
  - Add new descriptive content
  - Remove non-portal objects
  - Change scene meaning

--------------------------------------------------
OUTPUT FORMAT (JSON ONLY)
--------------------------------------------------

{
  "prompt": <string>,   // always output this, even if ok=true
  "valid": true/false,  // true if original prompt is valid
}

If no errors exist, "errors" MUST be an empty object {}.
If ok=true, fixed_prompt should be identical to the input prompt (verbatim).
Respond ONLY with the JSON object, no extra text.
"""