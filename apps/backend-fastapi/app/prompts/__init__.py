"""Jinja2 template loading for LLM prompts."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent),
    autoescape=select_autoescape(disabled_extensions=("jinja",), default=False),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render(template_name: str, **context: object) -> str:
    """Render ``template_name`` (e.g. ``classifier.v1.jinja``) with ``context``."""
    return _env.get_template(template_name).render(**context)
