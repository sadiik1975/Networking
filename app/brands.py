"""Brands the networking is done on behalf of. Edit descriptions to match your pitch."""
from app.config import settings


def get_brands() -> dict[str, dict]:
    return {
        "borough_build": {
            "name": "Borough Build",
            "url": settings.borough_build_url,
            "pitch": "a minority-owned digital agency specializing in web design, AI agent integrations and automation",
            "keywords": ("website", "web", "app", "ai", "automation", "digital", "brand", "software", "seo", "design"),
            "offerings": {
                "web_design": "web application development and UI design",
                "ai_agent_integration": "custom AI agent integrations and automations",
                "full_digital_agency": "web development, AI automation, branding and digital strategy",
            },
        },
        "been_ventures": {
            "name": "Been Ventures",
            "url": settings.been_ventures_url,
            "pitch": "a venture company building AI-assisted business tools and connectors",
            "keywords": ("ai", "automation", "software", "platform", "data", "integration", "connector", "startup", "tool"),
            "offerings": {
                "ai_tools": "AI-assisted business tools and connectors",
                "partnership": "partnerships and joint ventures",
                "platform_integration": "platform and data integrations",
            },
        },
    }


BRAND_KEYS = ("borough_build", "been_ventures")
