from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('agregar_voluntario/', views.agregar_voluntario, name='agregar_voluntario'),
    path('registrar_asistencia/', views.registrar_asistencia, name='registrar_asistencia'),
    path('exportar_excel/', views.exportar_asistencias_excel, name='exportar_excel'),
    path('reporte_graficas/', views.generar_reporte_graficas, name='reporte_graficas'),
    path('areas/', views.lista_areas, name='lista_areas'),
    path('areas/agregar/', views.agregar_area, name='agregar_area'),
    path('areas/editar/<int:area_id>/', views.editar_area, name='editar_area'),
]