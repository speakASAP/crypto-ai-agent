from app.dependencies.auth import has_crypto_entitlement


def test_accepts_crypto_user_role():
    assert has_crypto_entitlement({"roles": ["app:crypto-ai-agent:user"]}) is True


def test_accepts_crypto_admin_role():
    assert has_crypto_entitlement({"roles": ["app:crypto-ai-agent:admin"]}) is True


def test_rejects_marathon_only_role():
    assert has_crypto_entitlement({"roles": ["app:marathon:user"]}) is False


def test_rejects_missing_or_malformed_roles():
    assert has_crypto_entitlement({}) is False
    assert has_crypto_entitlement({"roles": "app:crypto-ai-agent:user"}) is False
