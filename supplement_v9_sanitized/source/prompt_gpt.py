import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SCENE_OBJECTS = [
    "blue cube",
    "blue moon",
    "yellow pentagon",
    "yellow star",
    "red pentagon",
    "red moon",
    "green cube",
    "green star",
]
OBJECT_SYNONYMS = {
    "blue crescent": "blue moon",
    "red crescent": "red moon",
    "green crescent": "green moon",
    "yellow crescent": "yellow moon",
    "yellow hexagon": "yellow pentagon",
    "red hexagon": "red pentagon",
    "green hexagon": "green pentagon",
    "blue hexagon": "blue pentagon",
}


def canonicalize_text(text):
    normalized = text.strip().lower()
    normalized = normalized.strip("`'\" \n\t")
    normalized = normalized.replace("_", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    for source, target in OBJECT_SYNONYMS.items():
        normalized = normalized.replace(source, target)
    return normalized


def canonicalize_object(text):
    normalized = canonicalize_text(text)
    if normalized in SCENE_OBJECTS:
        return normalized
    for candidate in SCENE_OBJECTS:
        if candidate in normalized:
            return candidate
    raise ValueError(f"Could not map codex response to a known object: {text!r}")


def _mask_push_corner_image(image_path):
    import cv2
    import numpy as np

    image_path = Path(image_path).resolve()
    masked_path = image_path.with_name(f"{image_path.stem}_mask{image_path.suffix}")
    image_bytes = np.fromfile(str(image_path), dtype=np.uint8)
    image = cv2.imdecode(image_bytes, cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"Cannot read image for push-corner mask: {image_path}")
    cv2.circle(image, np.array([310, 164]), 100, (0, 0, 0), -1)
    success, encoded = cv2.imencode(masked_path.suffix or ".png", image)
    if not success:
        raise RuntimeError(f"Cannot encode masked push-corner image: {masked_path}")
    encoded.tofile(str(masked_path))
    return masked_path


def _complete(client, prompt, image_paths=None):
    response = client.complete(prompt, image_paths=image_paths)
    return canonicalize_text(response)


def get_interactive_object(client, sentence):
    prompt = f"""
Task: Identify the interactive object in the sentence.

Rules:
- The object must be one item from this closed set:
  {", ".join(SCENE_OBJECTS)}.
- If the sentence says "move your arm to the left/right/top/bottom of X", the interactive object is X.
- Return exactly one object name and nothing else.

Sentence:
{sentence}
""".strip()
    return canonicalize_object(_complete(client, prompt))


def get_subtask_make_line(client, current_image_path):
    example_1 = PROJECT_ROOT / "prompt_examples" / "top_right" / "0.jpg"
    example_2 = PROJECT_ROOT / "prompt_examples" / "top_right" / "16.jpg"
    prompt = """
You are a robot planning assistant for a tabletop manipulation task.

Attached images are in this order:
1. Example image 1
2. Example image 2
3. Current observation

Example labels:
- Image 1 -> "1) Move the red circle to the left of the yellow hexagon ..."
- Image 2 -> "1) Move your arm to the bottom of the green cube ..."

Task:
- Decompose the current scene into a short plan for arranging blocks into a line.
- Return only the first sub-task.
- Use only the verbs "Move" or "Push".
- Use only objects from the current scene.
- Output exactly one sentence.
""".strip()
    return _complete(client, prompt, image_paths=[example_1, example_2, current_image_path])


def get_subtask_push_corner(client, current_image_path, excluding=None):
    example_dir = PROJECT_ROOT / "prompt_examples" / "bottom_right_lt"
    example_images = [
        example_dir / "frame_0.png",
        example_dir / "frame_14.png",
        example_dir / "frame_33.png",
        example_dir / "frame_113.png",
        example_dir / "frame_128.png",
        example_dir / "frame_513.png",
    ]

    exclusion_text = ""
    if excluding:
        if isinstance(excluding, (list, tuple, set)):
            excluded = ", ".join(str(item) for item in excluding)
        else:
            excluded = str(excluding)
        exclusion_text = f"\n- Do not choose: {excluded}."

    prompt = f"""
You are a robot planning assistant for a push-to-corner task.

Attached images are in this order:
1. Example image 1 -> "Move your arm to the left of green moon."
2. Example image 2 -> "Push the blue moon into blue cube."
3. Example image 3 -> "Push the blue cube to the bottom left corner."
4. Example image 4 -> "Move your arm to the left of yellow pentagon."
5. Example image 5 -> "Push the yellow pentagon to the bottom left corner."
6. Example image 6 -> "Move the arm to the red star."
7. Current observation

Task:
- The scene objects are restricted to: {", ".join(SCENE_OBJECTS)}.
- Choose only the best first sub-task for moving blocks to the bottom left corner.
- Return exactly one sentence.
- Use only the verbs "Move" or "Push".
- Do not return a full plan.{exclusion_text}
""".strip()
    return _complete(client, prompt, image_paths=[*example_images, current_image_path])


def get_subtask_group_color(client, current_image_path):
    raise NotImplementedError("group_color is not implemented in this repository.")


def get_subtasks(image_path, client, task="make_line", excluding=None):
    image_path = Path(image_path).resolve()

    if task == "make_line":
        return get_subtask_make_line(client=client, current_image_path=image_path)
    if task == "push_corner":
        masked_path = _mask_push_corner_image(image_path)
        return get_subtask_push_corner(
            client=client,
            current_image_path=masked_path,
            excluding=excluding,
        )
    if task == "group_color":
        return get_subtask_group_color(client=client, current_image_path=image_path)
    raise ValueError(f"Unsupported task: {task}")
