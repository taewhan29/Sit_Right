"""Single-call integration of posture logic and warning effects.

Construct and call on the main/UI thread. Camera acquisition stays with caller.
"""
from .controller import PostureController


class PostureMonitor:
    def __init__(self, reference_pose=None, settings=None, *, preview_only=False,
                 effects=None):
        self.controller = PostureController(settings)
        self.closed = False
        if reference_pose is not None:
            self.controller.set_reference(reference_pose)
        if effects is None:
            from .effects import WarningEffects
            effects = WarningEffects(preview_only=preview_only)
        self.effects = effects

    def set_reference(self, reference_pose):
        if self.closed:
            raise RuntimeError('Monitor is closed.')
        reference = self.controller.set_reference(reference_pose)
        self.effects.clear()
        return reference

    def update(self, current_pose, frame=None, *, now=None):
        """One call per frame calculates posture and applies all warning effects."""
        if self.closed:
            raise RuntimeError('Monitor is closed.')
        try:
            result = self.controller.update(current_pose, now=now)
            self.effects.update(result, frame=frame)
            return result
        except Exception:
            self.close()
            raise

    def close(self):
        if not self.closed:
            self.closed = True
            self.effects.close()

    def __enter__(self):
        if self.closed:
            raise RuntimeError('Monitor is closed.')
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False
