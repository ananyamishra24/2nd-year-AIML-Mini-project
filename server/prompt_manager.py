"""
Prompt Management Framework
────────────────────────────
Versioned prompt templates with personalization support.
Manages story generation prompts and image prompts.
"""

import json
import logging
from typing import Optional

logger = logging.getLogger('brave_story.prompts')

# ── Prompt version ───────────────────────────────────────────────────
PROMPT_VERSION = '2.0.0'


# ── Story generation prompt ──────────────────────────────────────────

def build_story_prompt(child_name: str, age: int, gender: str,
                       condition: str, hero_characteristics: str = '',
                       preferences: Optional[list] = None,
                       story_history: Optional[list] = None,
                       story_length: str = '', tone: str = '',
                       theme: str = '', villain_type: str = '',
                       ending_type: str = '', illustration_style: str = '',
                       reading_level: str = '') -> str:
    """
    Build a personalized story generation prompt.
    Incorporates child preferences, story history, and custom settings.
    """

    # Age-adapted instructions (can be overridden by reading_level)
    effective_level = reading_level
    if not effective_level:
        if age <= 4:
            effective_level = 'toddler'
        elif age <= 7:
            effective_level = 'early-reader'
        elif age <= 12:
            effective_level = 'older-child'
        else:
            effective_level = 'teen'

    # Determine page count from story_length setting or default by level
    page_counts = {
        'short': 1,
        'medium': 3,
        'long': 5,
    }
    level_defaults = {
        'toddler': 3,
        'early-reader': 3,
        'older-child': 4,
        'teen': 5,
    }
    num_pages = page_counts.get(story_length, level_defaults.get(effective_level, 3))

    level_instructions = {
        'toddler': (
            "Use very simple words and short sentences. "
            "Playful, gentle tone. "
            f"Generate exactly {num_pages} page(s). "
            "Each page should be 2-3 sentences max. "
            "Use lots of sound words and fun repetition."
        ),
        'early-reader': (
            "Use simple words and short sentences. "
            "Playful, gentle tone. "
            f"Generate exactly {num_pages} page(s). "
            "Each page should be 2-4 sentences max. "
            "Use lots of sound words and fun repetition."
        ),
        'older-child': (
            "Use moderate vocabulary with engaging storytelling. "
            "Include dialogue and adventure elements. "
            f"Generate exactly {num_pages} page(s). "
            "Each page should be 4-6 sentences."
        ),
        'teen': (
            "Use natural, age-appropriate language with motivational themes. "
            "Include character growth and emotional depth. "
            f"Generate exactly {num_pages} page(s). "
            "Each page should be 5-8 sentences."
        ),
    }
    age_instructions = level_instructions.get(effective_level, level_instructions['early-reader'])

    # Hero characteristics block
    traits_block = ''
    if hero_characteristics:
        traits_block = f"""
HERO CHARACTERISTICS:
The hero {child_name} must consistently display these personality traits: {hero_characteristics}.
These traits should:
- Shape the hero's decisions and actions throughout the story
- Be demonstrated through specific moments and dialogue
- Connect meaningfully to how they overcome their medical challenge
- Provide moral lessons and inspirational messaging
"""

    # Personalization block (based on learned preferences)
    personalization_block = ''
    if preferences:
        liked_themes = [p['preference_value'] for p in preferences
                       if p['preference_type'] == 'theme' and p.get('total_weight', 0) > 0]
        liked_characters = [p['preference_value'] for p in preferences
                           if p['preference_type'] == 'character_type' and p.get('total_weight', 0) > 0]
        liked_settings = [p['preference_value'] for p in preferences
                         if p['preference_type'] == 'setting' and p.get('total_weight', 0) > 0]

        parts = []
        if liked_themes:
            parts.append(f"- Themes this child enjoys: {', '.join(liked_themes[:5])}")
        if liked_characters:
            parts.append(f"- Character types they like: {', '.join(liked_characters[:5])}")
        if liked_settings:
            parts.append(f"- Settings they prefer: {', '.join(liked_settings[:5])}")

        if parts:
            personalization_block = (
                "\nPERSONALIZATION (learned from previous stories):\n"
                + '\n'.join(parts) +
                "\nTry to incorporate these preferences while keeping the story fresh and unique.\n"
            )

    # History awareness
    history_block = ''
    if story_history and len(story_history) > 0:
        prev_titles = [h.get('story_title', '') for h in story_history[:5] if h.get('story_title')]
        if prev_titles:
            history_block = f"""
STORY HISTORY:
This child has previously enjoyed these stories: {', '.join(prev_titles)}.
Create something NEW and different — avoid repeating the same plot or theme.
"""

    # Custom settings block
    settings_block = ''
    settings_parts = []
    if tone:
        tone_map = {
            'funny': 'Make the story funny and humorous with silly moments and jokes.',
            'adventurous': 'Make the story action-packed and exciting with an adventurous tone.',
            'calming': 'Make the story calm, soothing, and gentle — perfect for bedtime.',
            'educational': 'Include educational elements and fun facts woven into the narrative.',
        }
        settings_parts.append(tone_map.get(tone, f'Use a {tone} tone throughout.'))
    if theme:
        theme_map = {
            'superhero': 'Set in a superhero universe with capes, powers, and a heroic mission.',
            'space': 'Set in outer space with planets, stars, rockets, and alien friends.',
            'underwater': 'Set in an underwater world with coral reefs, friendly sea creatures, and hidden treasures.',
            'jungle': 'Set in a lush jungle with exotic animals, vines, and ancient mysteries.',
            'fairy-tale': 'Set in a magical fairy-tale kingdom with castles, enchanted forests, and magical creatures.',
            'dinosaur': 'Set in a prehistoric dinosaur world with friendly dinosaurs and volcanic landscapes.',
        }
        settings_parts.append(theme_map.get(theme, f'Set the story in a {theme} world.'))
    if villain_type:
        villain_map = {
            'monster': 'Portray the medical challenge as a silly, non-scary monster that the hero defeats.',
            'storm': 'Portray the medical challenge as a storm that the hero learns to weather and calm.',
            'puzzle': 'Portray the medical challenge as an exciting puzzle or riddle the hero cleverly solves.',
            'shadow': 'Portray the medical challenge as a shadow that the hero bravely shines light upon.',
        }
        settings_parts.append(villain_map.get(villain_type, f'The challenge appears as {villain_type}.'))
    if ending_type:
        ending_map = {
            'triumphant': 'End with a triumphant, celebratory victory.',
            'peaceful': 'End with a peaceful, serene, and heartwarming resolution.',
            'cliffhanger': 'End with an exciting cliffhanger that teases a future adventure.',
        }
        settings_parts.append(ending_map.get(ending_type, f'End with a {ending_type} ending.'))
    if illustration_style:
        style_map = {
            'cartoon': 'Describe image prompts as bright cartoon-style illustrations.',
            'watercolor': 'Describe image prompts as soft watercolor-style paintings.',
            'comic-book': 'Describe image prompts as bold comic-book panel illustrations.',
            'pixel-art': 'Describe image prompts as retro pixel-art style illustrations.',
        }
        settings_parts.append(style_map.get(illustration_style, f'Use {illustration_style} illustration style.'))
    if settings_parts:
        settings_block = '\nCUSTOM SETTINGS:\n' + '\n'.join(f'- {p}' for p in settings_parts) + '\n'

    # Main prompt
    prompt = f"""You are a compassionate children's story writer specializing in medical-sensitive storytelling.

Write a personalized children's story for a {age}-year-old {gender} named {child_name} who has {condition}.

AGE ADAPTATION:
{age_instructions}

CORE REQUIREMENTS:
- The story must be empowering, turning the condition/treatment into a superpower or magical ability
- The tone must ALWAYS be warm, reassuring, brave, and supportive
- NEVER include scary, violent, or hopeless elements
- Medical procedures should be described gently and positively
- The child hero must triumph and feel proud at the end
- Include a gentle educational element about their condition
{traits_block}{personalization_block}{history_block}{settings_block}
CONTENT SAFETY RULES:
- No death, violence, or frightening scenarios
- No explicit medical procedures or graphic descriptions
- No stigmatization of the medical condition
- Treatment and care should be framed positively
- All characters should be supportive and kind
- End on a hopeful, empowering note

Return ONLY valid JSON with this exact structure:
{{
  "title": "Story Title",
  "theme": "adventure|friendship|discovery|courage|magic",
  "pages": [
    {{
      "text": "Page text here...",
      "imagePrompt": "Detailed illustration description for this page. Cartoon style, colorful, child-friendly."
    }}
  ]
}}
"""
    logger.info(f'Built story prompt v{PROMPT_VERSION} for {child_name} (age {age})')
    return prompt


# ── Image prompt builder ─────────────────────────────────────────────

def build_image_prompt(base_prompt: str, child_name: str, age: int,
                       gender: str, page_number: int, total_pages: int,
                       illustration_style: str = '') -> str:
    """Build a safe, consistent image generation prompt."""

    style_presets = {
        'watercolor': (
            "Soft watercolor painting style. "
            "Delicate brush strokes and pastel washes. "
            "Gentle color bleeding and blending. "
            "Dreamy atmospheric look. "
        ),
        'comic-book': (
            "Bold comic book illustration style. "
            "Strong outlines and dynamic poses. "
            "Vibrant saturated colors. "
            "Action-panel composition. "
        ),
        'pixel-art': (
            "Retro pixel art style illustration. "
            "Chunky pixel aesthetic. "
            "Bright 16-bit color palette. "
            "Clean pixel-perfect edges. "
        ),
    }
    custom_prefix = style_presets.get(illustration_style, '')

    style_guidance = (
        f"{custom_prefix}"
        "Children’s storybook illustration style."
        "Warm glowing lighting."
        "Magical cozy atmosphere."
        "Round cute cartoon characters with big expressive eyes."
        "Soft outlines and gentle shading."
        "Dreamy soft background."
        "Whimsical hand-drawn digital art."
        "2D storybook illustration style."
        "Bright warm color palette."
        "Soft gradients and smooth textures."
        "Fluffy clouds and playful environment."
        "Friendly and comforting mood."
        "Safe and suitable for toddlers and young children."
        "High detail illustration."
        "Storybook page composition."
        "Cinematic framing."
        "NO text, letters, or words in the image."
        "NO scary elements."
        "NO medical equipment visible."
        "NO realistic human faces."
    )

    # Character consistency note
    consistency = (
        f"The main character is a {age}-year-old {gender} named {child_name}. "
        "Keep the character's appearance consistent across all illustrations. "
    )

    prompt = f"{base_prompt}. {consistency} {style_guidance}"

    logger.debug(f'Built image prompt for page {page_number}/{total_pages}')
    return prompt


# ── Prompt for translation ───────────────────────────────────────────

def build_translation_prompt(text: str, target_lang: str) -> str:
    """Build a prompt for translating story text while preserving tone."""
    return f"""Translate the following children's story text to {target_lang}.
Preserve the warm, encouraging, and child-friendly tone.
Keep names unchanged. Maintain the same sentence structure.
Translate naturally — don't be too literal.

Text:
{text}
"""


# ── Prompt for personalization extraction ────────────────────────────

def build_preference_extraction_prompt(story_json: str, feedback: dict) -> str:
    """Build a prompt to extract preferences from a completed story session."""
    return f"""Analyze this children's story and reading session feedback to extract the child's preferences.

Story data: {story_json}
Feedback: {json.dumps(feedback)}

Return JSON with:
{{
  "themes": ["theme1", "theme2"],
  "character_types": ["type1"],
  "settings": ["setting1"],
  "story_elements": ["element1"]
}}
"""
