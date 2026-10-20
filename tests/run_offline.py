"""Run mocked tests in a sandbox where Windows socketpair is unavailable.

No-I/O loop: only suitable for the AsyncMock tests in this directory, never BLE.
Use standard unittest discovery on a normal development machine.
"""
import asyncio
import selectors
import unittest


class NoIOSelector(selectors.SelectSelector):
    def select(self, timeout=None):
        if self.get_map():
            raise RuntimeError("The offline test loop must not perform real I/O")
        return []


class NoIOLoop(asyncio.SelectorEventLoop):
    def __init__(self):
        super().__init__(NoIOSelector())

    def _make_self_pipe(self):
        pass

    def _close_self_pipe(self):
        pass

    def _write_to_self(self):
        pass


if __name__ == "__main__":
    import test_opal
    test_opal.CoordinatorTests.loop_factory = staticmethod(NoIOLoop)
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(test_opal))
    raise SystemExit(not result.wasSuccessful())
