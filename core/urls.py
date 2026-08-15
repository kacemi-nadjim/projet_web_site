from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("galerie/", views.galerie, name="galerie"),
    path("deposer/", views.upload, name="upload"),
    path("exporter/", views.exporter, name="exporter"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("lots/", views.batches, name="batches"),
    path("lots/creer/", views.batch_creer, name="batch_creer"),
    path("lots/<int:batch_id>/", views.batch_detail, name="batch_detail"),
    path("lots/<int:batch_id>/images/", views.batch_telecharger_images, name="batch_telecharger_images"),
    path("lots/<int:batch_id>/travail/", views.batch_telecharger_travail, name="batch_telecharger_travail"),
    path("contact/", views.contact, name="contact"),
    path("inscription/", views.demande_inscription, name="inscription"),
    path("mentions-legales/", views.mentions, name="mentions"),
    path("confidentialite/", views.confidentialite, name="confidentialite"),
    path("cgu/", views.cgu, name="cgu"),
    path("image/<int:image_id>/supprimer/", views.supprimer_image, name="supprimer_image"),
]
