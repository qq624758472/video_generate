DEFAULT_COMMON_STYLE_EN = (
    "Epic Buddhist fantasy cinema, celestial realm above the clouds, colossal golden Buddha, "
    "sacred atmosphere, floating heavenly palaces, fragrant flower rain, glowing colorful aura, "
    "Dunhuang flying apsaras circling in the air, divine ribbons, grand scale, majestic light, "
    "slow camera movement, highly cinematic, 16:9 widescreen."
)


SCENES = [
    (
        "jing1",
        "Inside a sacred cave-temple suspended above the clouds at dawn, a weathered hand gently brushes over palm-leaf sutra pages. "
        "The camera reveals the words 'Thus have I heard' glowing softly while candle flames sway in the spiritual wind. "
        "The view slowly pulls back to reveal Ananda seated in reverent silence, with monks recording scriptures behind him.",
    ),
    (
        "jing2",
        "In the celestial vision of ancient India near Sravasti, vast misty forests, sala trees, and mango groves spread beneath a sea of clouds. "
        "Soft sunbeams pierce the dawn mist, and the distant monastery appears like a holy sanctuary between heaven and earth. "
        "A very slow aerial camera movement glides across the landscape with solemn peace.",
    ),
    (
        "jing3",
        "Outside the monastic dwellings in the holy dawn, wooden doors open one by one and monks in reddish-brown robes step out quietly in perfect order. "
        "They adjust robes and clean alms bowls as flower petals drift through the air. "
        "The camera follows them at eye level with calm sacred realism.",
    ),
    (
        "jing4",
        "The central wooden door opens and the Buddha emerges with serene expression and immeasurable dignity. "
        "He slowly arranges his robe, lifts a simple alms bowl, and steps barefoot onto cool stone slabs that shine with faint golden light. "
        "Every gesture is calm, precise, and filled with spiritual gravity.",
    ),
    (
        "jing5",
        "The Buddha walks at the head of the assembly while monks follow in perfect formation toward the city. "
        "The procession passes through an ancient gate into a living world of merchants, women, children, brahmins, and beggars. "
        "People respectfully bow, offer food, and the Buddha responds with compassionate stillness.",
    ),
    (
        "jing6",
        "A cross-cut montage shows the Buddha receiving alms equally from all beings. "
        "A poor woman offers a little coarse rice from a clay jar, while a wealthy household presents rich food. "
        "The Buddha accepts both with the same compassion, never taking more than needed, while monks continue their orderly alms round.",
    ),
    (
        "jing7",
        "Before noon, under bright and gentle sunlight, the Buddha and the monks return from the city to Jetavana. "
        "The camera follows from behind as their shadows stretch across the ground and the noise of the worldly streets fades away. "
        "They move back toward trees, silence, and sacred calm.",
    ),
    (
        "jing8",
        "In a quiet forest clearing, the Buddha and the monks sit and eat in silence. "
        "Close shots show the Buddha eating carefully without wasting even a grain, cleaning the bowl afterward, folding the robes neatly, "
        "and then walking barefoot to clear water to wash the dust from his feet.",
    ),
    (
        "jing9",
        "After washing his feet, the Buddha returns to a great tree, lays out a grass mat with his own hands, and slowly sits in meditation. "
        "His posture becomes as steady as an ancient mountain while the monks sit behind him in complete stillness. "
        "Sunlight filters through leaves as the camera slowly pulls back into a vast sacred tableau.",
    ),
]


def build_prompt(scene_prompt: str, common_style: str = "", negative_prompt: str = "") -> str:
    style = (common_style or DEFAULT_COMMON_STYLE_EN).strip()
    prompt = f"{scene_prompt} {style}".strip()
    if negative_prompt.strip():
        prompt = f"{prompt} Avoid: {negative_prompt.strip()}."
    return prompt


def get_scene(output_name: str) -> tuple[str, str]:
    for name, prompt in SCENES:
        if name == output_name:
            return name, build_prompt(prompt)
    raise KeyError(f"unknown scene: {output_name}")


def build_variant_prompt(
    scene_prompt: str,
    variant_index: int,
    common_style: str = "",
    negative_prompt: str = "",
    variant_notes: dict[int, str] | None = None,
) -> str:
    default_notes = {
        1: "Version A: majestic establishing composition, slow and solemn movement, emphasize grandeur and sacred calm.",
        2: "Version B: more character-focused composition, richer depth, stronger emotional atmosphere, elegant cinematic detail.",
    }
    notes = variant_notes or default_notes
    note = notes.get(variant_index, "Alternate cinematic composition for the same scene.")
    return f"{build_prompt(scene_prompt, common_style=common_style, negative_prompt=negative_prompt)} {note}".strip()
