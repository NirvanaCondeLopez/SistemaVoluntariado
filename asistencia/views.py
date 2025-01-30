from django.http import JsonResponse, HttpResponse
from django.utils import timezone

import json
from django.views.decorators.csrf import csrf_exempt
from .models import Area
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from io import BytesIO
import base64
from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import ValidationError
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from django.core.paginator import Paginator

def index(request):
    """
    Vista principal que muestra la lista de voluntarios y sus asignaciones.
    """
    voluntarios = Voluntario.objects.all().order_by('nombre')
    asignaciones = Asignacion.objects.all().order_by('-fecha', '-entrada')
    return render(request, 'asistencia/index.html', {
        'voluntarios': voluntarios,
        'asignaciones': asignaciones
    })

def agregar_voluntario(request):
    """
    Vista para agregar un nuevo voluntario.
    """
    areas = Area.objects.all()  # Obtener todas las áreas disponibles

    if request.method == 'POST':
        # Obtener datos del formulario
        nombre = request.POST.get('nombre')
        identificacion = request.POST.get('identificacion')
        email = request.POST.get('email')
        tipo = request.POST.get('tipo')

        # Validar que todos los campos estén presentes
        if not all([nombre, identificacion, email, tipo]):
            return render(request, 'asistencia/agregar_voluntario.html', {
                'error': 'Todos los campos son obligatorios.',
                'areas': areas
            })

        try:
            # Crear y guardar el voluntario
            voluntario = Voluntario(
                nombre=nombre,
                identificacion=identificacion,
                email=email,
                tipo=tipo
            )
            voluntario.full_clean()  # Validar el modelo antes de guardar
            voluntario.save()  # Guardar el voluntario en la base de datos

            # Obtener la URL del código QR generado
            qr_code_url = voluntario.qr_code.url

            # Renderizar la plantilla con el código QR disponible para descargar
            return render(request, 'asistencia/agregar_voluntario.html', {
                'success': 'Voluntario agregado correctamente.',
                'qr_code_url': qr_code_url,
                'areas': areas
            })

        except ValidationError as e:
            return render(request, 'asistencia/agregar_voluntario.html', {
                'error': str(e),
                'areas': areas
            })
        except Exception as e:
            return render(request, 'asistencia/agregar_voluntario.html', {
                'error': 'Ocurrió un error al guardar el voluntario.',
                'areas': areas
            })

    # Si no es una solicitud POST, mostrar el formulario
    return render(request, 'asistencia/agregar_voluntario.html', {
        'areas': areas
    })

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from .models import Voluntario, Asignacion
from django.utils import timezone

@csrf_exempt
def registrar_asistencia(request):
    """
    Vista para registrar la asistencia de un voluntario mediante su código QR.
    Permite dos escaneadas por voluntario: una para entrada y otra para salida.
    """
    if request.method == 'POST':
        identificacion = request.POST.get('identificacion')

        if not identificacion:
            return JsonResponse({
                'status': 'error',
                'message': 'No se proporcionó una identificación válida.'
            }, status=400)

        try:
            # Buscar al voluntario por su identificación (ignorando mayúsculas/minúsculas y espacios)
            voluntario = Voluntario.objects.get(identificacion__iexact=identificacion.strip())

            # Obtener la fecha actual
            fecha_actual = timezone.now().date()

            # Buscar si ya tiene una asignación de entrada registrada hoy
            asignacion, created = Asignacion.objects.get_or_create(
                voluntario=voluntario,
                fecha=fecha_actual,
                defaults={'entrada': timezone.now().time()}
            )

            if not created and not asignacion.salida:
                asignacion.salida = timezone.now().time()
                asignacion.save()
                return JsonResponse({
                    'status': 'success',
                    'message': f'Salida registrada para {voluntario.nombre}.',
                    'voluntario': {
                        'nombre': voluntario.nombre,
                        'identificacion': voluntario.identificacion,
                        'tipo': voluntario.get_tipo_display(),
                    }
                })
            elif created:
                return JsonResponse({
                    'status': 'success',
                    'message': f'Entrada registrada para {voluntario.nombre}.',
                    'voluntario': {
                        'nombre': voluntario.nombre,
                        'identificacion': voluntario.identificacion,
                        'tipo': voluntario.get_tipo_display(),
                    }
                })
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': 'El voluntario ya registró su entrada y salida hoy.'
                }, status=400)

        except Voluntario.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': f'Voluntario con identificación {identificacion} no encontrado.'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'Ocurrió un error inesperado: {str(e)}'
            }, status=500)

    # Si no es una solicitud POST, mostrar la página de registro de asistencia
    return render(request, 'asistencia/registrar_asistencia.html')

def exportar_asistencias_excel(request):
    """
    Vista para exportar las asignaciones a un archivo Excel.
    """
    # Obtener todas las asignaciones
    asignaciones = Asignacion.objects.all().values(
        'voluntario__nombre',
        'voluntario__identificacion',
        'voluntario__tipo',
        'voluntario__area__nombre',
        'fecha',
        'entrada',
        'salida'
    )

    # Convertir a DataFrame de pandas
    df = pd.DataFrame(asignaciones)

    # Crear un archivo Excel en memoria
    response = HttpResponse(content_type='application/ms-excel')
    response['Content-Disposition'] = 'attachment; filename="asignaciones.xlsx"'

    # Guardar el DataFrame en el archivo Excel
    with pd.ExcelWriter(response, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Asignaciones')

    return response

def generar_reporte_graficas(request):
    """
    Vista para generar reportes con gráficas de las asignaciones.
    """
    # Obtener los filtros del request
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    tipo_voluntario = request.GET.get('tipo_voluntario')

    # Filtrar las asignaciones
    asignaciones = Asignacion.objects.all().values(
        'voluntario__nombre',
        'voluntario__tipo',
        'voluntario__area__nombre',
        'fecha',
        'entrada',
        'salida'
    )

    if fecha_inicio:
        asignaciones = asignaciones.filter(fecha__gte=fecha_inicio)
    if fecha_fin:
        asignaciones = asignaciones.filter(fecha__lte=fecha_fin)
    if tipo_voluntario:
        asignaciones = asignaciones.filter(voluntario__tipo=tipo_voluntario)

    # Convertir a DataFrame de pandas
    df = pd.DataFrame(asignaciones)

    # Verificar si el DataFrame está vacío
    if df.empty:
        return render(request, 'asistencia/reporte_graficas.html', {
            'mensaje': 'No se encontraron datos para generar el reporte con los filtros seleccionados.'
        })

    # Gráfica 1: Asignaciones por tipo de voluntario
    plt.figure(figsize=(10, 6))
    sns.countplot(data=df, x='voluntario__tipo', palette='viridis')
    plt.title('Asignaciones por Tipo de Voluntario')
    plt.xlabel('Tipo de Voluntario')
    plt.ylabel('Cantidad de Asignaciones')

    # Guardar la gráfica en un buffer
    buffer_tipo = BytesIO()
    plt.savefig(buffer_tipo, format='png')
    buffer_tipo.seek(0)
    image_png_tipo = buffer_tipo.getvalue()
    buffer_tipo.close()

    # Convertir la gráfica a base64
    grafica_tipo = base64.b64encode(image_png_tipo).decode('utf-8')

    # Gráfica 2: Asignaciones por área
    plt.figure(figsize=(10, 6))
    sns.countplot(data=df, x='voluntario__area__nombre', palette='magma')
    plt.title('Asignaciones por Área')
    plt.xlabel('Área')
    plt.ylabel('Cantidad de Asignaciones')

    # Guardar la gráfica en un buffer
    buffer_area = BytesIO()
    plt.savefig(buffer_area, format='png')
    buffer_area.seek(0)
    image_png_area = buffer_area.getvalue()
    buffer_area.close()

    # Convertir la gráfica a base64
    grafica_area = base64.b64encode(image_png_area).decode('utf-8')

    # Exportar a Excel
    if 'export_excel' in request.GET:
        response = HttpResponse(content_type='application/ms-excel')
        response['Content-Disposition'] = 'attachment; filename="reporte_asignaciones.xlsx"'
        with pd.ExcelWriter(response, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Asignaciones', index=False)
        return response

    # Exportar a PDF
    if 'export_pdf' in request.GET:
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="reporte_asignaciones.pdf"'
        p = canvas.Canvas(response, pagesize=letter)
        p.drawString(100, 750, "Reporte de Asignaciones")

        # Agregar gráficas al PDF
        p.drawImage(ImageReader(BytesIO(base64.b64decode(grafica_tipo))), 100, 500, width=400, height=300)
        p.drawImage(ImageReader(BytesIO(base64.b64decode(grafica_area))), 100, 200, width=400, height=300)
        p.showPage()
        p.save()
        return response

    # Renderizar la plantilla con las gráficas
    return render(request, 'asistencia/reporte_graficas.html', {
        'grafica_tipo': grafica_tipo,
        'grafica_area': grafica_area
    })

def lista_areas(request):
    """
    Vista para listar todas las áreas con paginación.
    """
    areas_list = Area.objects.all()
    paginator = Paginator(areas_list, 8)
    page_number = request.GET.get('page')
    areas = paginator.get_page(page_number)
    return render(request, 'asistencia/lista_areas.html', {'areas': areas})

def agregar_area(request):
    """
    Vista para agregar una nueva área.
    """
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        capacidad_maxima = request.POST.get('capacidad_maxima')

        if not all([nombre, capacidad_maxima]):
            return render(request, 'asistencia/agregar_editar_area.html', {
                'error': 'Todos los campos son obligatorios.'
            })

        try:
            # Crear y guardar el área
            area = Area(nombre=nombre, capacidad_maxima=capacidad_maxima)
            area.full_clean()  # Validar el modelo antes de guardar
            area.save()

            return redirect('lista_areas')  # Redirigir a la lista de áreas
        except ValidationError as e:
            return render(request, 'asistencia/agregar_editar_area.html', {
                'error': str(e)
            })
        except Exception as e:
            return render(request, 'asistencia/agregar_editar_area.html', {
                'error': 'Ocurrió un error al guardar el área.'
            })

    # Si no es una solicitud POST, mostrar el formulario
    return render(request, 'asistencia/agregar_editar_area.html')

def editar_area(request, area_id):
    """
    Vista para editar un área existente.
    """
    area = get_object_or_404(Area, id=area_id)

    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        capacidad_maxima = request.POST.get('capacidad_maxima')

        if not all([nombre, capacidad_maxima]):
            return render(request, 'asistencia/agregar_editar_area.html', {
                'error': 'Todos los campos son obligatorios.',
                'area': area
            })

        try:
            # Actualizar el área
            area.nombre = nombre
            area.capacidad_maxima = capacidad_maxima
            area.full_clean()  # Validar el modelo antes de guardar
            area.save()

            return redirect('lista_areas')  # Redirigir a la lista de áreas
        except ValidationError as e:
            return render(request, 'asistencia/agregar_editar_area.html', {
                'error': str(e),
                'area': area
            })
        except Exception as e:
            return render(request, 'asistencia/agregar_editar_area.html', {
                'error': 'Ocurrió un error al guardar el área.',
                'area': area
            })

    # Si no es una solicitud POST, mostrar el formulario con los datos actuales
    return render(request, 'asistencia/agregar_editar_area.html', {
        'area': area
    })

