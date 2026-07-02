"""Rule registry tests."""

from aegis_incidents.rules.registry import DETECTION_RULE_REGISTRY_V1


def test_registry_has_seven_rules() -> None:
    assert len(DETECTION_RULE_REGISTRY_V1.rules) == 7


def test_rule_ids_are_unique() -> None:
    ids = [rule.rule_id for rule in DETECTION_RULE_REGISTRY_V1.rules]
    assert len(ids) == len(set(ids))


def test_all_rules_reference_valid_features() -> None:
    from aegis_ml.features.schema_registry import FEATURE_NAMES

    allowed = set(FEATURE_NAMES) | {"alert_count"}
    for rule in DETECTION_RULE_REGISTRY_V1.rules:
        for feature in rule.input_features:
            assert feature in allowed
