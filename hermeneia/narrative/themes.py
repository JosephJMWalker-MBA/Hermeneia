# Backwards-compatibility shim. Import from profiles.py instead.
from .profiles import (  # noqa: F401
    BUILT_IN_PROFILES as BUILT_IN_THEMES,
    seed_built_in_profiles as seed_built_in_themes,
    get_profile as get_theme,
    list_profiles as list_themes,
)
