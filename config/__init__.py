# Patch Django BaseContext.__copy__ for compatibility with Python 3.14+
try:
    from django.template.context import BaseContext

    def _patched_basecontext_copy(self):
        cls = self.__class__
        obj = cls.__new__(cls)
        obj.__dict__ = self.__dict__.copy()
        obj.dicts = self.dicts[:]
        return obj

    BaseContext.__copy__ = _patched_basecontext_copy
except Exception:
    pass
