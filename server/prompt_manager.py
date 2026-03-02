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
                       story_history: Optional[list] = None) -> str:
    """
    Build a personalized story generation prompt.
    Incorporates child preferences and story history for personalization.
    """

    # Age-adapted instructions
    if age <= 7:
        age_instructions = (
            "Use very simple words and short sentences. "
            "Playful, gentle tone. Generate exactly 3 pages. "
            "Each page should be 2-4 sentences max. "
            "Use lots of sound words and fun repetition."
        )
    elif age <= 12:
        age_instructions = (
            "Use moderate vocabulary with engaging storytelling. "
            "Include dialogue and adventure elements. Generate exactly 4 pages. "
            "Each page should be 4-6 sentences."
        )
    else:
        age_instructions = (
            "Use natural, age-appropriate language with motivational themes. "
            "Include character growth and emotional depth. Generate exactly 5 pages. "
            "Each page should be 5-8 sentences."
        )

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
{traits_block}{personalization_block}{history_block}
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
                       gender: str, page_number: int, total_pages: int) -> str:
    """Build a safe, consistent image generation prompt."""

    style_guidance = (
        "Children’s storybook illustration style."
        "Soft watercolor and pastel art style."
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
