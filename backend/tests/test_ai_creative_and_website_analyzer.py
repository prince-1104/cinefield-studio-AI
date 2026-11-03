"""Unit tests for Website Analysis, SSRF Defense, and Claude Creative Director."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.schemas.creative_ai import (
    CreativeBriefRequest,
    WebsiteAnalysisRequest,
    WebsiteAssetCandidate,
    WebsiteAnalysisResult,
)
from app.services.creative_director import ClaudeCreativeDirector
from app.services.website_analyzer import (
    RobustContentExtractor,
    analyze_website,
    validate_safe_url,
)


def test_ssrf_protection_blocks_private_networks():
    """Verify validate_safe_url rejects localhost, private IPs, and cloud metadata."""
    with pytest.raises(ValueError, match="Access to internal host"):
        validate_safe_url("http://localhost/test")

    with pytest.raises(ValueError, match="Access to internal host"):
        validate_safe_url("http://metadata.google.internal")

    with pytest.raises(ValueError, match="restricted network address"):
        validate_safe_url("http://127.0.0.1:8080/admin")

    with pytest.raises(ValueError, match="restricted network address"):
        validate_safe_url("http://169.254.169.254/latest/meta-data")

    with pytest.raises(ValueError, match="restricted network address"):
        validate_safe_url("http://10.0.0.1/internal")

    with pytest.raises(ValueError, match="Unsupported URL protocol"):
        validate_safe_url("ftp://example.com/file")


def test_html_content_extractor():
    """Test extracting title, meta description, headings, brand colors, and images."""
    html_sample = """
    <!DOCTYPE html>
    <html>
      <head>
        <title>Apex Dynamics – Autonomous Flight Vehicles</title>
        <meta name="description" content="Next-generation autonomous VTOL flight systems for enterprise.">
        <meta name="theme-color" content="#7c3aed">
        <meta property="og:image" content="https://example.com/hero_banner.jpg">
        <link rel="icon" href="/favicon.png">
      </head>
      <body>
        <header>
          <img src="/assets/logo.png" alt="Apex Brand Logo" class="brand-logo" />
        </header>
        <main>
          <h1>Revolutionizing Air Logistics</h1>
          <h2>Zero Emission Propulsion</h2>
          <p>We build photorealistic electric autonomous aircraft engineered for heavy cargo and extreme reliability.</p>
          <img src="/products/vtol_v1.jpg" alt="Apex VTOL Drone" />
        </main>
      </body>
    </html>
    """

    parser = RobustContentExtractor("https://example.com")
    parser.feed(html_sample)

    assert "Apex Dynamics" in "".join(parser.title_parts)
    assert parser.meta_desc == "Next-generation autonomous VTOL flight systems for enterprise."
    assert parser.theme_color == "#7c3aed"
    assert "Revolutionizing Air Logistics" in parser.headings
    assert len(parser.logo_urls) >= 1
    assert any("logo.png" in url for url, _ in parser.logo_urls)
    assert len(parser.product_image_urls) >= 1


@pytest.mark.asyncio
async def test_claude_creative_director_structured_generation():
    """Verify Claude transforms a vague prompt into a structured production brief."""
    director = ClaudeCreativeDirector(api_key="mock-key")

    mock_claude_response = {
        "product_name": "Apex Pulse EV",
        "brief": "A cinematic launch film chronicling an electric hypercar surging through illuminated tunnels and coastal mountain passes.",
        "tone": "photorealistic, cinematic, dramatic, futuristic, neon anamorphic",
        "audience": "High-net-worth automotive enthusiasts and luxury tech pioneers",
        "cta": "Electrify Your Reality. Reserve on ApexMotors.com",
        "suggested_music_mood": "Deep cinematic synthwave building into orchestral percussion",
        "hook": "A silent headlight ignite illuminating a rain-slicked racetrack",
        "narration_preview": "Speed is no longer measured in fuel. It is born in pure current.",
        "creative_reasoning": "Emphasizes luxury performance and silent power through contrasting lighting.",
    }

    with patch.object(director, "_call_claude_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_claude_response

        req = CreativeBriefRequest(
            prompt="A sleek electric supercar commercial",
            video_category="Product Launch",
            target_duration=60,
            aspect_ratio="16:9",
        )

        result = await director.generate_brief(req)

        assert result.product_name == "Apex Pulse EV"
        assert result.target_duration == 60
        assert result.shot_count == 8
        assert result.aspect_ratio == "16:9"
        assert result.video_category == "Product Launch"
        assert result.provider_used == "claude"
        assert "synthwave" in result.suggested_music_mood

