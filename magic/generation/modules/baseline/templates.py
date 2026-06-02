# -*- coding: utf-8 -*-

BASELINE_TEMPLATE = """<context>
A user prompt <<inputs.prompt>> describing a scene is provided.
</context>

<objective>
Based on the provided user prompt, generate a complete scene by filling in the placeholders in the JSON structure below.
</objective>

<style>
JSON
</style>

<tone>
Creative and imaginative while trying your best to maintain realism and physical plausibility.
However, you **MUST** strictly adhere to the user's requirements, and thus realism can be broken if the user requires so.
</tone>

<audience>
A demanding professional scene designer who validates and checks your output.
</audience>

<response>
{output_guidance}

<structure>
{{
  "scene_type": "indoor/outdoor",
  "regions": {{
    "<<FILL_IN_REGION_NAME>>": {{
      "floor": {{"color": "<<FILL_IN>>", "material": "<<FILL_IN>>", "attributes": "<<FILL_IN>>", "roughness": <<FILL_IN_FLOAT>>, "metallic": <<FILL_IN_FLOAT>>}},
      "wall": {{"color": "<<FILL_IN>>", "material": "<<FILL_IN>>", "attributes": "<<FILL_IN>>", "roughness": <<FILL_IN_FLOAT>>, "metallic": <<FILL_IN_FLOAT>>}},
      "shape": {{
        "min_vertex": [<<FILL_IN_X>>, <<FILL_IN_Y>>],
        "max_vertex": [<<FILL_IN_X>>, <<FILL_IN_Y>>],
        "height": <<FILL_IN>>
      }},
      "objects": {{
        "<<FILL_IN_OBJECT_NAME>>": {{
          "category": "<<FILL_IN>>",
          "is_portal": <<FILL_IN_BOOL>>,
          "supported_from_below": <<FILL_IN_BOOL>>,
          "hanged_on_wall": <<FILL_IN_BOOL>>,
          "hanged_from_ceiling": <<FILL_IN_BOOL>>,
          "color": "<<FILL_IN>>",
          "material": "<<FILL_IN>>",
          "attributes": "<<FILL_IN>>",
          "dimensions": [<<FILL_IN_WIDTH>>, <<FILL_IN_HEIGHT>>, <<FILL_IN_DEPTH>>],
          "position": [<<FILL_IN_X>>, <<FILL_IN_Y>>, <<FILL_IN_Z>>],
          "rotation": [<<FILL_IN_X>>, <<FILL_IN_Y>>, <<FILL_IN_Z>>],
          "children": {{}}
        }},
        ...
      }},
      "object_relations": [
        ["<<FILL_IN_OBJECT_NAME_1>>", "<<FILL_IN_RELATIONSHIP>>", "<<FILL_IN_OBJECT_NAME_2>>"],
        ...
      ]
      "lights": [[<<FILL_IN_X>>, <<FILL_IN_Y>>, <<FILL_IN_Z>>], ...]
    }},
    ...
  }},
  "connections": [
    {{
      "type": "door/window",
      "color": "<<FILL_IN>>",
      "material": "<<FILL_IN>>",
      "attributes": "<<FILL_IN>>",
      "dimensions": [<<FILL_IN_WIDTH>>, <<FILL_IN_HEIGHT>>, <<FILL_IN_DEPTH>>],
      "position_x": <<FILL_IN>>,
      "position_y": <<FILL_IN>>,
      "position_z": <<FILL_IN>>,
      "rotation_y": <<FILL_IN>>
    }},
    ...
  ]
}}
</structure>
</response>

<inputs>
<prompt>
{prompt}
</prompt>
</inputs>"""
