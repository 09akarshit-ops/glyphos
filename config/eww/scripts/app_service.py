"""Importable shared app service; CLI entry retains a readable hyphenated filename."""
import importlib.util
from pathlib import Path
_spec=importlib.util.spec_from_file_location('glyphos_app_service',Path(__file__).with_name('app-service.py'))
_module=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
globals().update({key:value for key,value in vars(_module).items() if not key.startswith('_')})
