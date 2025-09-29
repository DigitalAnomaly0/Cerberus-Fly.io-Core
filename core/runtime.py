
import os, importlib

def _load_class(module_path: str, class_name: str):
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)

def get_providers():
    """Return (Governor, Seeder, Antithesis, mode) where mode in {'real','demo'}.
    If CERBERUS_IMPL is set to a module base (e.g., 'cerberus_pkg'), we attempt:
      cerberus_pkg.governor.Governor
      cerberus_pkg.seeder.Seeder
      cerberus_pkg.antithesis.Antithesis
    Fallback to demo providers if import fails.
    """
    impl = os.getenv("CERBERUS_IMPL")
    if impl:
        try:
            Gov = _load_class(f"{impl}.governor", "Governor")
            Sd  = _load_class(f"{impl}.seeder", "Seeder")
            Anti= _load_class(f"{impl}.antithesis", "Antithesis")
            return Gov, Sd, Anti, "real"
        except Exception:
            pass
    # Fallback: demo providers
    from .models import DemoGovernor as Gov, DemoSeeder as Sd, DemoAntithesis as Anti
    return Gov, Sd, Anti, "demo"
