import pytest
from app.services.ai_service import AIService, VALID_NECKLINE, VALID_RISE


def test_parse_populates_cut_attributes():
    svc = AIService(endpoints=[{"name": "x", "url": "http://x/v1", "vision_model": "m", "text_model": "m"}])
    resp = (
        '{"type":"dress","subtype":"a-line","primary_color":"navy","colors":["navy"],'
        '"pattern":"solid","material":null,"formality":"casual","style":["classic"],'
        '"season":["all-season"],"fit":"regular","neckline":"v-neck","rise":null,'
        '"silhouette":"a-line","sleeve_length":"short"}'
    )
    tags = svc._parse_tags_from_response(resp)
    assert tags.neckline == "v-neck"
    assert tags.silhouette == "a-line"
    assert tags.sleeve_length == "short"
    assert tags.rise is None


def test_parse_rejects_out_of_vocab_attribute():
    svc = AIService(endpoints=[{"name": "x", "url": "http://x/v1", "vision_model": "m", "text_model": "m"}])
    resp = '{"type":"top","neckline":"banana","sleeve_length":"short"}'
    tags = svc._parse_tags_from_response(resp)
    assert tags.neckline is None       # not in VALID_NECKLINE -> dropped
    assert tags.sleeve_length == "short"
