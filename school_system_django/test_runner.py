from django.test.runner import DiscoverRunner

class ManagedModelTestRunner(DiscoverRunner):
    """
    Test runner that dynamically overrides '_meta.managed = False' 
    to 'True' for testing unmanaged legacy models.
    """
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        from django.apps import apps
        for model in apps.get_models():
            model._meta.managed = True
