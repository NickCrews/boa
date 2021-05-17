class Scale:
    """Abstract base class for a scale."""

    def __init__(self):
        raise NotImplementedError("Cannot instantiate the abstract class Scale")

    def open(self):
        """Must be called before calls to read(). Can be called multiple times."""
        pass

    def is_open(self):
        """Retuns whether the Scale is open or not."""
        raise NotImplementedError("is_open() must be overriden in subclasses")

    def close(self):
        """Perform any needed cleanup. Can be called multiple times, at any time."""
        pass

    def read(self):
        """Return an iterable of (time.time(), value) tuples. Value is an int."""
        return []


class ScaleSearcher:
    """Base class for a service that provides Scales as data sources.

    Since Scales are system-wide resources, there should only be one of each
    Scale, and therefore there should only be a single ScaleSearcher to
    manage all of them. Therefore make a ScaleSearcher a global singleton by
    preventing instantiation. Use it as a class, eg ``ScaleSearcher.available_scales()``
    """

    def __new__(cls, *args, **kwargs):
        raise NotImplementedError(
            "Cannot create {} instance, just use it as a class".format(cls)
        )

    @classmethod
    def available_scales(cls):
        """Returns an iterable of `Scale` objects."""
        return []
