"""Separate urlconf module so the farmer-only catalog URLs can be mounted
under /farmer/ with their own namespace, distinct from the public
catalog URLs mounted at /."""
from .urls import farmer_urlpatterns

app_name = "farmer_catalog"
urlpatterns = farmer_urlpatterns
