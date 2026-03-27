COMMON_STYLE_EN = (
    "Realistic Buddhist cinematic style, quiet and restrained mood, soft morning light, "
    "natural color grading, slow aerial movement, ancient India setting, atmospheric mist, "
    "documentary realism, 16:9 widescreen."
)


SCENES = [
    (
        "jing1",
        "Inside a dim stone cave at dawn, a weathered hand gently brushes over palm-leaf sutra pages. "
        "The fingers pause on the words 'Thus have I heard'. Candlelight flickers softly. "
        "The camera slowly pulls back from the scripture to reveal Ananda in a plain robe sitting quietly, "
        "while monks behind him calmly record the text.",
    ),
    (
        "jing2",
        "Early morning in ancient India, mist covers the countryside near Sravasti. "
        "Rows of sala trees and mango groves stretch into the distance. "
        "Soft sunlight breaks through the fog in gentle beams. "
        "Monastic dwellings of Jetavana are faintly visible among the trees, "
        "with the distant outline of the city wall under a pale dawn sky. "
        "A realistic aerial shot moves very slowly and peacefully across the landscape.",
    ),
    (
        "jing3",
        "Outside the monks' quarters in ancient India at dawn, wooden doors open one after another. "
        "Monks in reddish-brown robes quietly step out in an orderly way, adjusting robes and cleaning bowls. "
        "Fallen leaves cover the ground. The camera follows at eye level with calm documentary realism.",
    ),
]


def build_prompt(scene_prompt: str) -> str:
    return f"{scene_prompt} {COMMON_STYLE_EN}"


def get_scene(output_name: str) -> tuple[str, str]:
    for name, prompt in SCENES:
        if name == output_name:
            return name, build_prompt(prompt)
    raise KeyError(f"unknown scene: {output_name}")
