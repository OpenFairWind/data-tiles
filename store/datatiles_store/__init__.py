def create_app(config_object=None):
    from .app import create_app as factory
    return factory(config_object)

__all__ = ["create_app"]
