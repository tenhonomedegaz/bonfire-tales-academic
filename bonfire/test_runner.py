from django.test.runner import DiscoverRunner


class ApplicationDiscoverRunner(DiscoverRunner):
    """Discover the application tests without importing scratch scripts."""

    def build_suite(self, test_labels=None, **kwargs):
        return super().build_suite(test_labels or ['home'], **kwargs)
