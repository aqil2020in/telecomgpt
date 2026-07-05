"""ANR (Automatic Neighbor Relation) rules engine."""

from __future__ import annotations

from tnic.rules.engine import RuleDefinition, RuleEngine, _get


def _anr_rules() -> list[RuleDefinition]:
    cat = "anr"

    return [
        RuleDefinition(
            "anr_missing_neighbor", cat, "Missing neighbor relation",
            lambda k: (_get(k, "nr_neighbor_count") or 99) < 3,
            "Insufficient NR neighbors — HO failures from missing NCR",
            0.83,
            ["Enable ANR add function", "Manually add intra-frequency neighbors", "Re-run ANR discovery"],
            ["nr_neighbor_count", "ho_prep_fail_rate"],
        ),
        RuleDefinition(
            "anr_pci_conflict", cat, "PCI conflict / confusion",
            lambda k: (_get(k, "pci_conflict_count") or 0) > 0 or (_get(k, "pci_mod3_collision") or 0) > 0,
            "PCI conflict or mod-3 collision — interference and HO to wrong cell",
            0.85,
            ["Run PCI audit", "Enable ANR PCI optimization", "Update neighbor PCI list"],
            ["pci_conflict_count", "pci_mod3_collision"],
        ),
        RuleDefinition(
            "anr_stale_neighbor", cat, "Stale / blacklisted neighbor",
            lambda k: (_get(k, "anr_blacklist_count") or 0) > 0 or (_get(k, "stale_neighbor_pct") or 0) > 10,
            "Stale or blacklisted neighbors blocking mobility",
            0.79,
            ["Clear ANR blacklist after fix", "Remove decommissioned cells from NCL", "Validate ANR remove policy"],
            ["anr_blacklist_count", "stale_neighbor_pct"],
        ),
        RuleDefinition(
            "anr_ho_nbr_mismatch", cat, "HO failure correlated with neighbor gap",
            lambda k: (_get(k, "ho_prep_fail_rate") or 0) > 5 and (_get(k, "nr_neighbor_count") or 99) < 5,
            "High HO prep fail with sparse neighbor list — ANR gap",
            0.81,
            ["Add missing neighbors on HO corridor", "Audit ANR HO allow list", "Drive-test neighbor coverage overlap"],
            ["ho_prep_fail_rate", "nr_neighbor_count"],
        ),
        RuleDefinition(
            "anr_prach_conflict", cat, "PRACH root sequence conflict",
            lambda k: (_get(k, "prach_conflict_count") or 0) > 0,
            "PRACH root sequence collision with neighbor — access/HO impact",
            0.77,
            ["Replan PRACH root sequences", "Coordinate with ANR PCI/PRACH audit"],
            ["prach_conflict_count", "rach_msg1_fail_rate"],
        ),
    ]


ANR_RULE_ENGINE = RuleEngine("anr", _anr_rules())
