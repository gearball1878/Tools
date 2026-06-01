# Auto-generated compatibility wrapper for historical main_window monkey patches.
# The individual patch chunks are executed in the caller's globals to preserve
# the original behavior that used to live directly at the end of main_window.py.
from pathlib import Path


def apply_legacy_patches(target_globals):
    base = Path(__file__).with_name("legacy_patches")
    for patch_file in sorted(base.glob("patch_*.py")):
        code = patch_file.read_text(encoding="utf-8")
        exec(compile(code, str(patch_file), "exec"), target_globals, target_globals)

apply_legacy_patches(globals())
