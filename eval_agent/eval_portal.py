import io
import base64
import re, json

from openai import OpenAI
from PIL import Image
from pathlib import Path

NAMING_SYS_PROMPT = """
You are a strict and deterministic multi-view visual-name evaluator.

You are given (in order):
1. A candidate object name (representing a portal for scene transition).
2. A ground truth object name/type provided in the user prompt.

Your task:
Decide whether the candidate object's name refers to the same object as the ground truth.

General Principles:
- You evaluate ONLY the semantic meaning of the names.
- You MUST NOT hallucinate additional context beyond the names.
- If the identity of the candidate object cannot be confidently extracted, return "uncertain".

Evaluation Procedure:
1. Extract the core noun describing the main object from the candidate name.
2. Normalize for minor naming variations (e.g. plural/singular, common synonyms).
3. Determine semantic equivalence to the ground truth.

Matching Rules:
- Exact semantic match is required AFTER normalization.
- Normalize to base noun form before comparison.
- Singular and plural forms MUST be treated as identical (e.g., "chair" == "chairs", "door" == "doors").
- Minor variations and widely accepted synonyms are allowed.
- Category-level mismatch MUST be considered incorrect.
- If the object identity remains ambiguous or overly broad, return "uncertain".

Confidence Scoring:
- 1.0 = explicit, unambiguous semantic equivalence.
- 0.7-0.9 = strong match with minor wording differences.
- 0.4-0.6 = ambiguous, partial or uncertain match
- 0.0-0.3 = clear mismatch.

Output Format (STRICT JSON ONLY):
{
  "detected_object": "<best noun describing the candidate name>",
  "ground_truth": "<the EXACT ground truth object provided in the prompt>",
  "match": true | false | "uncertain",
  "confidence": <float from 0.0 to 1.0>,
  "reasoning": "<brief, strictly name-based justification>"
}

Important:
- Output JSON only. No extra explanation.
- Work strictly from the names.
- If unsure whether the candidate object corresponds to the ground truth, choose "uncertain".
"""

IMG_SYS_PROMPT = """
You are a strict and deterministic multi-view visual evaluator.

You are given  (in order):
1. Some images (at most eight) of the same object captured from different orbit viewpoints (front, back, left, right, and diagonal angles).
2. A ground truth object name/type provided in the user prompt.

Facts:
- All the images depict the same physical object.
- The images are independent multi-angle captures, not sequential frames.
- The object may be partially occluded in some views but should be visually consistent across most views.

Your task:
Determine whether the object shown in the images matches the ground truth object. Ensure your identification describes exactly one dominant object.

General Principles:
- You evaluate ONLY visual evidence.
- You MUST NOT infer details not visible in the images.
- Ignore background elements unless they are necessary for object identification.
- If the object cannot be confidently identified, return "uncertain".

Evaluation Procedure:
1. Analyze all the views jointly.
2. Identify the single most consistently visible, centered, and dominant object.
3. Use the multi-angle evidence to infer shape, structure, material, color, and functional cues.
4. Extract the most precise noun or noun phrase representing the object.
5. Judge semantic equivalence between detected object and ground truth.

Matching Rules:
- Exact semantic match is required AFTER normalization.
- Minor naming variations and common synonyms are acceptable.
- Category-level mismatch MUST be treated as
- Normalize to base noun form before comparison.
- Singular and plural forms MUST be treated as identical (e.g., "chair" == "chairs", "door" == "doors").
- Category-level mismatch MUST be considered incorrect.
- If multiple objects appear, choose the most consistently centered/primary object across views.
- If identity remains ambiguous or insufficiently visible, return "uncertain".

Confidence Scoring:
- 1.0 = clear and unambiguous identification across multiple angles.
- 0.7-0.9 = strong match with minor uncertainty.
- 0.4-0.6 = ambiguous or unclear → set "match" to "uncertain".
- 0.0-0.3 = clear mismatch.

Output Format (STRICT JSON ONLY):
{
  "detected_object": "<best noun describing the visual object>",
  "ground_truth": "<EXACT ground truth object from prompt>",
  "match": true | false | "uncertain",
  "confidence": <float from 0.0 to 1.0>,
  "reasoning": "<brief justification referencing multi-view visual evidence>"
}

Important:
- Output JSON only. No extra text.
- Do not describe the images in prose beyond what is needed for justification.
- If unsure whether the candidate object corresponds to the ground truth, choose "uncertain".
"""

def sample_frames(image_files, max_frames=8):
    total = len(image_files)

    if total <= max_frames:
        return image_files

    # uniform sampling
    indices = [
        int(i * total / max_frames)
        for i in range(max_frames)
    ]
    return [image_files[i] for i in indices]

def encode_image_small(img_path, max_size=512, quality=70):
    img = Image.open(img_path).convert("RGB")

    # resize while keeping aspect ratio
    img.thumbnail((max_size, max_size))

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=quality, optimize=True)

    return base64.b64encode(buffer.getvalue()).decode("utf-8")

def completion_with_backoff(client, **kwargs):
    return client.chat.completions.create(**kwargs)

def query_name(system_msg, prompt, p_name: str, client, model):

    messages = list(system_msg)

    messages.append({
        "role": "user",
        "content": [
            {"type": "text", "text": p_name},
            {"type": "text", "text": prompt}
        ]
    })

    response = client.chat.completions.create(
        model=model,
        messages=messages,
    )

    try:
        result = parse_llm_dict(response.choices[0].message.content)
    except Exception:
        print("[WARN] Analysis result not a valid JSON, keeping raw string")
    return result

def query_frames(system_msg, prompt, img_dir: Path, client, model):

    messages = list(system_msg)
    img_dir = Path(img_dir)

    image_files = sorted(img_dir.glob("*.png")) + sorted(img_dir.glob("*.jpg"))

    if len(image_files) == 0:
        return ({
        "detected_object": "none",
        "ground_truth": prompt.split(": ")[1],
        "match": "uncertain",
        "confidence": 0,
        "reasoning": "none"
    })

    # reduce frame rate
    sampled_files = sample_frames(image_files, max_frames=8)

    image_contents = []

    for img_path in sampled_files:
        img_base64 = encode_image_small(img_path, max_size=512, quality=70)

        image_contents.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{img_base64}"
            }
        })

    messages.append({
        "role": "user",
        "content": [
            *image_contents,
            {"type": "text", "text": prompt}
        ]
    })

    response = client.chat.completions.create(
        model=model,
        messages=messages,
    )

    try:
        result = parse_llm_dict(response.choices[0].message.content)
    except Exception:
        print("[WARN] Analysis result not a valid JSON, keeping raw string")
    return result
    
def sys_msg(sys_prompt):
    """Form system messages"""
    sys_msg = [{"role": "system", "content": sys_prompt}]
    return sys_msg


def parse_llm_dict(text):
    if isinstance(text, dict):
        return text

    text = text.strip().replace("```json", "").replace("```", "")

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found")

    json_str = match.group(0)

    return json.loads(json_str)

def parse_llm_list(text):
    text = text.strip().replace("```json", "").replace("```", "")

    match = re.search(r"\[.*?\]", text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, list):
                return parsed
        except:
            pass

    match = re.search(r"\{.*?\}", text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return [parsed]
        except:
            pass

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
        elif isinstance(parsed, dict):
            return [parsed]
    except:
        pass

    print("[ERROR] Failed to parse LLM output:")
    print(text)
    raise ValueError("Invalid JSON format from LLM")

def match_leftover(version, portals, data, llm_bag):

    client = OpenAI(api_key=llm_bag["normal_llm"].api_key)

    prompt = f"""
    You are given:

    1. Ground truth portal types:
    {json.dumps(portals)}

    2. Generated portal data:
    """

    if version == "ab2":
        prompt += "\nEach item is a portal name:\n"
        for i, d in enumerate(data):
            prompt += f"{i}: {d}\n"
    else:
        prompt += "\nEach item is a portal with multi-view images.\n"
        prompt += "You will receive images for each index.\n"

    prompt += f"""

    Your task:
    - Assign EACH data item to ONE ground truth portal.
    - Every ground truth portal MUST be assigned to AT LEAST ONE data item if there are more data items than ground truth portals.
    - Multiple data items MAY map to the same ground truth (duplication allowed).
    - Perform global reasoning to maximize correct matches.

    For EACH data item:
    - Identify the object
    - Compare with assigned ground truth
    - Output analysis as a LIST OF DICTIONARIES

    Output STRICT JSON LIST (same order as data):

    [
    {{
        "detected_object": "...",
        "ground_truth": "...",
        "match": true | false | "uncertain",
        "confidence": float,
        "reasoning": "..."
    }},
    ...
    ]
    """

    if version == "ab2":
        system_msg = [{"role": "system", "content": NAMING_SYS_PROMPT}]
        messages = system_msg + [{"role": "user", "content": prompt}]
    else:
        system_msg = [{"role": "system", "content": IMG_SYS_PROMPT}]

        content = [{"type": "text", "text": prompt}]
        for idx, img_dir in enumerate(data):
            image_files = sorted(Path(img_dir).glob("*.png")) + sorted(Path(img_dir).glob("*.jpg"))
            sampled = sample_frames(image_files, max_frames=8)

            for img_path in sampled:
                img_base64 = encode_image_small(img_path)
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}
                })

        messages = system_msg + [{"role": "user", "content": content}]

    original_messages = messages
    response = client.chat.completions.create(
        model=llm_bag["normal_llm"].model,
        messages=messages,
    )

    result = parse_llm_list(response.choices[0].message.content)

    assigned_gt = set(r["ground_truth"] for r in result)
    missing = [gt for gt in portals if gt not in assigned_gt]
    if missing and (len(portals) < len(data)):
        print("[WARN] Missing GT coverage:", missing)

        fix_prompt = f"""
        The following ground truth portals were not assigned:
        {missing}

        Fix the assignment so that EACH ground truth appears at least once.
        Return full corrected JSON list.
        """

        response2 = client.chat.completions.create(
            model=llm_bag["normal_llm"].model,
            messages = original_messages + [{
                "role": "user",
                "content": fix_prompt
            }]
        )

        result = parse_llm_list(response2.choices[0].message.content)

    if len(result) != len(data):
        print("[WARN] Output length mismatch")
        fix_prompt = f"""
        {len(data)} analysis expected, {len(result)} generated.
        """

        response2 = client.chat.completions.create(
            model=llm_bag["normal_llm"].model,
            messages = original_messages + [{
                "role": "user",
                "content": fix_prompt
            }]
        )

        result = parse_llm_list(response2.choices[0].message.content)


    return result

def portal_analyzer(version: str, portal: str, p_name: str = None, img_path: str = None, llm_bag=None):
    client = OpenAI(api_key=llm_bag["normal_llm"].api_key)

    print(f"[RUN] Evaluating {portal}")

    if version == "ab2":
        naming_sys_msg = sys_msg(NAMING_SYS_PROMPT)
        result = query_name(naming_sys_msg, f"ground_truth: {portal}", p_name, client, llm_bag["normal_llm"].model)
    else:
        img_sys_msg = sys_msg(IMG_SYS_PROMPT)
        result = query_frames(img_sys_msg, f"ground_truth: {portal}", img_path, client, llm_bag["normal_llm"].model)

    try:
        result["ground_truth"] = portal
    except:
        print("ground truth not found.")

    return result