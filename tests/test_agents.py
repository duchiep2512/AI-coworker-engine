"""
Tests for individual NPC agents — persona loading and trait verification.
"""

import pytest
from app.personas.traits import get_persona, PERSONA_REGISTRY

class TestPersonaRegistry:
    def test_all_three_agents_registered(self):
        assert "CEO" in PERSONA_REGISTRY
        assert "CHRO" in PERSONA_REGISTRY
        assert "RegionalManager" in PERSONA_REGISTRY

    def test_ceo_persona_has_traits(self):
        ceo = get_persona("CEO")
        assert ceo.agent_id == "CEO"
        assert "visionary" in ceo.personality_traits
        assert "protective_of_brand_dna" in ceo.personality_traits
        assert len(ceo.hidden_constraints) >= 3

    def test_chro_persona_has_traits(self):
        chro = get_persona("CHRO")
        assert chro.agent_id == "CHRO"
        assert "empathetic" in chro.personality_traits
        assert "competency_framework" in chro.knowledge_scope

    def test_regional_manager_persona(self):
        rm = get_persona("RegionalManager")
        assert rm.agent_id == "RegionalManager"
        assert "practical" in rm.personality_traits
        assert "regional_rollout" in rm.knowledge_scope

    def test_invalid_agent_raises_error(self):
        with pytest.raises(ValueError, match="Unknown agent"):
            get_persona("InvalidAgent")

    def test_each_agent_has_display_name(self):
        for agent_id, config in PERSONA_REGISTRY.items():
            assert config.display_name, f"{agent_id} missing display_name"
            assert config.role_title, f"{agent_id} missing role_title"
