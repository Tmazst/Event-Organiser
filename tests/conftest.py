import pytest


@pytest.fixture(autouse=True)
def enable_vendor_features_for_tests(request):
    """Keep existing marketplace tests explicit while production defaults stay off."""
    if "app" not in request.fixturenames:
        return
    app = request.getfixturevalue("app")
    app.config["VENDOR_FEATURE_ENABLED"] = True
    app.config["VENDOR_STORE_MANAGEMENT_ENABLED"] = True
