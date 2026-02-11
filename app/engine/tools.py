"""
NPC Tools — Simulated business tools that AI Co-workers can use.

Includes KPI Calculator, A/B Scenario Simulator, Competency Lookup,
Resource Estimator, and Regional Data Lookup.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import json

from app.core.logging import logger

#  TOOL DEFINITIONS (For LangGraph tool calling)

class ToolName(Enum):
    """Available tools that NPC agents can invoke."""
    KPI_CALCULATOR = "calculate_program_kpis"
    AB_SIMULATOR = "simulate_ab_scenarios"
    COMPETENCY_LOOKUP = "lookup_competency_framework"
    RESOURCE_ESTIMATOR = "estimate_resources"
    REGIONAL_DATA = "get_regional_hr_data"

#  KPI CALCULATOR

# Simulated baseline metrics for Gucci Group
BASELINE_METRICS = {
    "promotion_rate": 12.5,  # % annual
    "internal_mobility_rate": 8.2,  # % annual
    "leadership_satisfaction": 68.0,  # %
    "talent_retention": 82.0,  # %
    "time_to_proficiency_months": 18.0,
    "engagement_score": 72.0,  # %
    "360_participation_rate": 45.0,  # %
}

def calculate_program_kpis(
    program_type: str,
    target_population: int = 1000,
    implementation_quality: float = 0.8,
) -> Dict[str, Any]:
    """
    Calculate expected KPI improvements for a leadership development program.
    
    Args:
        program_type: Type of program (e.g., "360_feedback", "competency_framework", "coaching")
        target_population: Number of employees impacted
        implementation_quality: Quality factor 0.0-1.0
    
    Returns:
        Dict with baseline, projected, and delta metrics
    """
    logger.info(f"KPI Calculator invoked: {program_type} for {target_population} employees")
    
    # Impact multipliers by program type
    impact_map = {
        "360_feedback": {
            "leadership_satisfaction": 0.15,
            "engagement_score": 0.12,
            "360_participation_rate": 0.40,
            "talent_retention": 0.08,
        },
        "competency_framework": {
            "promotion_rate": 0.20,
            "time_to_proficiency_months": -0.25,  # Reduction is good
            "internal_mobility_rate": 0.18,
        },
        "coaching": {
            "leadership_satisfaction": 0.20,
            "engagement_score": 0.10,
            "talent_retention": 0.12,
        },
        "leadership_academy": {
            "promotion_rate": 0.25,
            "internal_mobility_rate": 0.22,
            "time_to_proficiency_months": -0.30,
            "talent_retention": 0.15,
        },
    }
    
    impacts = impact_map.get(program_type, impact_map["competency_framework"])
    
    # Calculate projected metrics
    result = {
        "program_type": program_type,
        "target_population": target_population,
        "implementation_quality": implementation_quality,
        "baseline_metrics": {},
        "projected_metrics": {},
        "expected_delta": {},
        "confidence_interval": "±15%",
        "notes": [],
    }
    
    for metric, baseline in BASELINE_METRICS.items():
        result["baseline_metrics"][metric] = baseline
        
        if metric in impacts:
            delta = baseline * impacts[metric] * implementation_quality
            projected = baseline + delta
            result["projected_metrics"][metric] = round(projected, 1)
            result["expected_delta"][metric] = f"{'+' if delta > 0 else ''}{round(delta, 1)}"
        else:
            result["projected_metrics"][metric] = baseline
            result["expected_delta"][metric] = "0"
    
    # Add contextual notes
    if implementation_quality < 0.6:
        result["notes"].append("Low implementation quality may reduce impact by 40%")
    if target_population > 5000:
        result["notes"].append("Large-scale rollout may require phased approach")
    
    return result

#  A-B SCENARIO SIMULATOR

@dataclass
class RolloutScenario:
    """Represents a rollout strategy for comparison."""
    name: str
    approach: str  # "big_bang", "phased", "pilot_first"
    timeline_months: int
    regions_included: List[str]
    budget_eur: int
    risk_level: str  # "low", "medium", "high"

def simulate_ab_scenarios(
    scenario_a: Dict[str, Any],
    scenario_b: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Compare two rollout scenarios and provide recommendation.
    
    Args:
        scenario_a: First scenario parameters
        scenario_b: Second scenario parameters
    
    Returns:
        Comparison analysis with recommendation
    """
    logger.info(f"A-B Simulator: Comparing {scenario_a.get('name')} vs {scenario_b.get('name')}")
    
    def score_scenario(scenario: Dict) -> Dict[str, Any]:
        """Score a scenario on multiple dimensions."""
        approach = scenario.get("approach", "phased")
        timeline = scenario.get("timeline_months", 12)
        budget = scenario.get("budget_eur", 500000)
        regions = len(scenario.get("regions_included", []))
        
        # Scoring logic
        scores = {
            "speed_score": max(0, 100 - (timeline * 5)),  # Faster = better
            "cost_efficiency": max(0, 100 - (budget / 10000)),  # Lower cost = better
            "risk_score": {"big_bang": 30, "phased": 70, "pilot_first": 90}.get(approach, 50),
            "coverage_score": min(100, regions * 15),
            "change_management_ease": {"big_bang": 40, "phased": 75, "pilot_first": 85}.get(approach, 60),
        }
        
        scores["overall"] = sum(scores.values()) / len(scores)
        return scores
    
    scores_a = score_scenario(scenario_a)
    scores_b = score_scenario(scenario_b)
    
    winner = "A" if scores_a["overall"] > scores_b["overall"] else "B"
    
    return {
        "scenario_a": {
            "config": scenario_a,
            "scores": scores_a,
        },
        "scenario_b": {
            "config": scenario_b,
            "scores": scores_b,
        },
        "recommendation": {
            "winner": winner,
            "winning_scenario": scenario_a if winner == "A" else scenario_b,
            "margin": abs(scores_a["overall"] - scores_b["overall"]),
            "key_differentiators": [],
        },
        "analysis": _generate_comparison_analysis(scenario_a, scores_a, scenario_b, scores_b),
    }

def _generate_comparison_analysis(
    a: Dict, scores_a: Dict, b: Dict, scores_b: Dict
) -> str:
    """Generate human-readable comparison analysis."""
    analysis_parts = []
    
    # Compare each dimension
    dimensions = ["speed_score", "cost_efficiency", "risk_score", "change_management_ease"]
    
    for dim in dimensions:
        diff = scores_a[dim] - scores_b[dim]
        if abs(diff) > 10:
            better = "A" if diff > 0 else "B"
            dim_name = dim.replace("_", " ").title()
            analysis_parts.append(f"Scenario {better} significantly better on {dim_name}")
    
    return "; ".join(analysis_parts) if analysis_parts else "Both scenarios are comparable"

#  COMPETENCY FRAMEWORK LOOKUP

VEPT_FRAMEWORK = {
    "Vision": {
        "description": "Ability to see beyond the immediate, anticipate trends, and inspire strategic direction",
        "junior_behaviors": [
            "Understands brand positioning within market context",
            "Can articulate team goals and their connection to brand vision",
            "Seeks to understand customer journey and brand touchpoints",
        ],
        "mid_behaviors": [
            "Develops 1-2 year strategic plans for their function",
            "Identifies emerging trends relevant to luxury market",
            "Translates brand vision into operational objectives",
        ],
        "senior_behaviors": [
            "Shapes long-term brand direction (3-5 year horizon)",
            "Anticipates market disruptions and positions brand accordingly",
            "Influences Group-level strategic decisions",
        ],
        "assessment_methods": ["360 feedback", "Strategic presentation", "Case study analysis"],
    },
    "Entrepreneurship": {
        "description": "Drive to innovate, take calculated risks, and create value",
        "junior_behaviors": [
            "Proposes improvements to existing processes",
            "Shows initiative in problem-solving",
            "Comfortable with ambiguity in new projects",
        ],
        "mid_behaviors": [
            "Launches new initiatives within budget constraints",
            "Takes ownership of innovation projects",
            "Builds business cases for new opportunities",
        ],
        "senior_behaviors": [
            "Creates new revenue streams or market approaches",
            "Challenges status quo at strategic level",
            "Sponsors innovation across the organization",
        ],
        "assessment_methods": ["Innovation portfolio review", "Risk-taking history", "P&L ownership"],
    },
    "Passion": {
        "description": "Deep connection to luxury, craftsmanship, and brand heritage",
        "junior_behaviors": [
            "Demonstrates genuine interest in brand history",
            "Advocates for quality and attention to detail",
            "Engages emotionally with product and customer experience",
        ],
        "mid_behaviors": [
            "Embodies brand values in daily interactions",
            "Inspires team with enthusiasm for brand mission",
            "Actively protects brand standards",
        ],
        "senior_behaviors": [
            "Serves as cultural ambassador for the brand",
            "Makes decisions that honor heritage while embracing innovation",
            "Creates emotional connection between brand and stakeholders",
        ],
        "assessment_methods": ["Cultural fit interview", "Brand knowledge assessment", "Team feedback"],
    },
    "Trust": {
        "description": "Ability to build authentic relationships and foster psychological safety",
        "junior_behaviors": [
            "Maintains confidentiality and follows through on commitments",
            "Communicates transparently with peers",
            "Admits mistakes and seeks feedback",
        ],
        "mid_behaviors": [
            "Creates safe environment for team to voice concerns",
            "Builds cross-functional relationships",
            "Handles conflict constructively",
        ],
        "senior_behaviors": [
            "Models vulnerability and authenticity at scale",
            "Builds trust across organizational boundaries",
            "Navigates complex stakeholder relationships with integrity",
        ],
        "assessment_methods": ["360 feedback on trust", "Team psychological safety survey", "Peer nominations"],
    },
}

def lookup_competency_framework(
    competency: Optional[str] = None,
    level: Optional[str] = None,  # "junior", "mid", "senior"
) -> Dict[str, Any]:
    """
    Look up details from the VEPT competency framework.
    
    Args:
        competency: Specific competency to look up (Vision, Entrepreneurship, Passion, Trust)
                   None returns all.
        level: Filter by seniority level
    
    Returns:
        Competency framework details
    """
    logger.info(f"Competency Lookup: {competency or 'all'} at {level or 'all levels'}")
    
    if competency and competency in VEPT_FRAMEWORK:
        result = {competency: VEPT_FRAMEWORK[competency].copy()}
    else:
        result = {k: v.copy() for k, v in VEPT_FRAMEWORK.items()}
    
    # Filter by level if specified
    if level:
        level_key = f"{level}_behaviors"
        for comp_name, comp_data in result.items():
            if level_key in comp_data:
                comp_data["behaviors"] = comp_data[level_key]
                # Keep only relevant level
                for l in ["junior", "mid", "senior"]:
                    key = f"{l}_behaviors"
                    if key in comp_data and key != level_key:
                        del comp_data[key]
    
    return {
        "framework": "VEPT (Vision, Entrepreneurship, Passion, Trust)",
        "source": "Gucci Group Talent & Leadership Development 2.0",
        "competencies": result,
        "note": "Behaviors should be assessed through multiple methods including 360 feedback",
    }

#  RESOURCE ESTIMATOR

def estimate_resources(
    program_type: str,
    target_headcount: int,
    regions: List[str],
    include_external_coaches: bool = False,
) -> Dict[str, Any]:
    """
    Estimate budget, timeline, and headcount for a leadership program.
    
    Args:
        program_type: Type of program
        target_headcount: Number of participants
        regions: List of regions to cover
        include_external_coaches: Whether external coaching is needed
    
    Returns:
        Resource estimation with breakdown
    """
    logger.info(f"Resource Estimator: {program_type} for {target_headcount} in {regions}")
    
    # Base costs per participant (EUR)
    base_costs = {
        "360_feedback": 150,
        "competency_framework": 80,
        "coaching": 2500,
        "leadership_academy": 3500,
        "train_the_trainer": 1200,
    }
    
    cost_per_person = base_costs.get(program_type, 500)
    
    # Regional multipliers
    regional_costs = {
        "Western Europe": 1.2,
        "Eastern Europe": 0.85,
        "Americas": 1.3,
        "APAC": 1.1,
        "Middle East": 1.15,
    }
    
    avg_multiplier = sum(regional_costs.get(r, 1.0) for r in regions) / len(regions) if regions else 1.0
    
    # Calculate totals
    program_cost = cost_per_person * target_headcount * avg_multiplier
    
    if include_external_coaches:
        coaching_cost = target_headcount * 800  # Per person coaching fee
        program_cost += coaching_cost
    
    # Timeline estimation
    timeline_base = {
        "360_feedback": 4,
        "competency_framework": 6,
        "coaching": 12,
        "leadership_academy": 18,
        "train_the_trainer": 3,
    }
    
    base_months = timeline_base.get(program_type, 6)
    region_months = len(regions) * 1.5  # Additional time per region
    timeline_months = int(base_months + region_months)
    
    # HR headcount needed
    hr_headcount = max(1, target_headcount // 200)
    
    return {
        "program_type": program_type,
        "target_headcount": target_headcount,
        "regions": regions,
        "budget": {
            "estimated_total_eur": int(program_cost),
            "per_participant_eur": int(program_cost / target_headcount),
            "breakdown": {
                "program_delivery": int(program_cost * 0.6),
                "technology_platform": int(program_cost * 0.15),
                "change_management": int(program_cost * 0.15),
                "contingency": int(program_cost * 0.10),
            },
        },
        "timeline": {
            "total_months": timeline_months,
            "phases": {
                "design": 2,
                "pilot": 3,
                "rollout": timeline_months - 5,
            },
        },
        "headcount": {
            "hr_team_fte": hr_headcount,
            "external_coaches": target_headcount // 20 if include_external_coaches else 0,
        },
        "assumptions": [
            "Based on luxury industry benchmarks",
            "Assumes existing HR infrastructure",
            "Does not include opportunity cost of participant time",
        ],
    }

#  REGIONAL HR DATA

REGIONAL_HR_DATA = {
    "France": {
        "headcount": 2800,
        "turnover_rate": 8.5,
        "avg_tenure_years": 7.2,
        "leadership_pipeline_strength": "Strong",
        "key_challenges": ["Union consultation required", "Formal HR processes expected"],
        "cultural_notes": "Hierarchical decision-making; expect documentation",
    },
    "Italy": {
        "headcount": 3200,
        "turnover_rate": 6.2,
        "avg_tenure_years": 9.5,
        "leadership_pipeline_strength": "Very Strong",
        "key_challenges": ["Family-style management culture", "Relationship-driven decisions"],
        "cultural_notes": "Build personal relationships; regional directors are key",
    },
    "UK": {
        "headcount": 1500,
        "turnover_rate": 12.1,
        "avg_tenure_years": 4.8,
        "leadership_pipeline_strength": "Moderate",
        "key_challenges": ["Post-Brexit talent mobility", "Competitive London market"],
        "cultural_notes": "Direct communication appreciated; merit-based culture",
    },
    "Germany": {
        "headcount": 1800,
        "turnover_rate": 7.8,
        "avg_tenure_years": 6.5,
        "leadership_pipeline_strength": "Strong",
        "key_challenges": ["Works council involvement", "Structured processes expected"],
        "cultural_notes": "Data-driven; expect detailed ROI analysis",
    },
    "USA": {
        "headcount": 2200,
        "turnover_rate": 15.3,
        "avg_tenure_years": 3.9,
        "leadership_pipeline_strength": "Moderate",
        "key_challenges": ["High competition for talent", "Diverse state regulations"],
        "cultural_notes": "Fast-paced; results-oriented; individual achievement valued",
    },
    "China": {
        "headcount": 1900,
        "turnover_rate": 18.5,
        "avg_tenure_years": 2.8,
        "leadership_pipeline_strength": "Developing",
        "key_challenges": ["Rapid growth outpacing talent", "Cultural adaptation of programs"],
        "cultural_notes": "Face-saving important; group harmony; digital-first approach",
    },
}

def get_regional_hr_data(
    region: Optional[str] = None,
    metric: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get HR metrics and insights for specific regions.
    
    Args:
        region: Specific region to query (None returns all)
        metric: Specific metric to filter on
    
    Returns:
        Regional HR data with insights
    """
    logger.info(f"Regional Data Lookup: {region or 'all regions'}, metric={metric or 'all'}")
    
    if region and region in REGIONAL_HR_DATA:
        data = {region: REGIONAL_HR_DATA[region]}
    else:
        data = REGIONAL_HR_DATA.copy()
    
    if metric:
        data = {
            k: {metric: v.get(metric)} for k, v in data.items() if metric in v
        }
    
    return {
        "regions": data,
        "last_updated": "Q4 2025",
        "source": "Gucci Group HR Analytics",
    }

#  TOOL REGISTRY (For LangGraph integration)

TOOL_REGISTRY = {
    ToolName.KPI_CALCULATOR.value: {
        "function": calculate_program_kpis,
        "description": "Calculate expected KPI improvements for leadership programs",
        "parameters": {
            "program_type": "Type: 360_feedback, competency_framework, coaching, leadership_academy",
            "target_population": "Number of employees affected",
            "implementation_quality": "Quality factor 0.0-1.0",
        },
    },
    ToolName.AB_SIMULATOR.value: {
        "function": simulate_ab_scenarios,
        "description": "Compare two rollout scenarios with recommendation",
        "parameters": {
            "scenario_a": "First scenario configuration",
            "scenario_b": "Second scenario configuration",
        },
    },
    ToolName.COMPETENCY_LOOKUP.value: {
        "function": lookup_competency_framework,
        "description": "Look up VEPT competency framework details",
        "parameters": {
            "competency": "Vision, Entrepreneurship, Passion, or Trust (optional)",
            "level": "junior, mid, or senior (optional)",
        },
    },
    ToolName.RESOURCE_ESTIMATOR.value: {
        "function": estimate_resources,
        "description": "Estimate budget, timeline, and headcount for programs",
        "parameters": {
            "program_type": "Type of program",
            "target_headcount": "Number of participants",
            "regions": "List of regions",
            "include_external_coaches": "Whether to include coaches",
        },
    },
    ToolName.REGIONAL_DATA.value: {
        "function": get_regional_hr_data,
        "description": "Get HR metrics for specific regions",
        "parameters": {
            "region": "Region name (optional)",
            "metric": "Specific metric (optional)",
        },
    },
}

def invoke_tool(tool_name: str, **kwargs) -> Dict[str, Any]:
    """
    Invoke a tool by name.
    
    Args:
        tool_name: Name of the tool to invoke
        **kwargs: Tool parameters
    
    Returns:
        Tool output
    """
    if tool_name not in TOOL_REGISTRY:
        return {"error": f"Unknown tool: {tool_name}"}
    
    try:
        func = TOOL_REGISTRY[tool_name]["function"]
        return func(**kwargs)
    except Exception as e:
        logger.error(f"Tool {tool_name} failed: {e}")
        return {"error": str(e)}
