from django.db import models
from django.core.validators import RegexValidator, EmailValidator
from django.utils.timezone import now
from io import BytesIO
import qrcode
from django.core.files import File

class Area(models.Model):
    """
    Modelo para representar un área y su capacidad máxima.
    """
    nombre = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Nombre del área',
        help_text='Ingrese el nombre del área.'
    )
    capacidad_maxima = models.PositiveIntegerField(
        verbose_name='Capacidad máxima',
        help_text='Ingrese la capacidad máxima para esta área.'
    )

    def __str__(self):
        return f"{self.nombre} (Capacidad: {self.capacidad_maxima})"

    def lugares_disponibles(self):
        """
        Retorna la cantidad de lugares disponibles en esta área.
        """
        asignados = self.asignacion_set.filter(salida__isnull=True).count()
        return max(self.capacidad_maxima - asignados, 0)

    class Meta:
        verbose_name = 'Área'
        verbose_name_plural = 'Áreas'
        ordering = ['nombre']


class Voluntario(models.Model):
    """
    Modelo para representar a un voluntario.
    """
    TIPO_OPCIONES = [
        ('Regular', 'Regular'),
        ('Especial', 'Especial'),
    ]

    nombre = models.CharField(
        max_length=100,
        verbose_name='Nombre completo',
        help_text='Ingrese el nombre completo del voluntario.'
    )
    identificacion = models.CharField(
        max_length=20,
        unique=True,
        verbose_name='Identificación',
        help_text='Ingrese la identificación del voluntario.',
        validators=[RegexValidator(regex='^[A-Za-z0-9]+$', message='Solo letras y números.')]
    )
    email = models.EmailField(
        unique=True,
        verbose_name='Correo electrónico',
        help_text='Ingrese el correo electrónico del voluntario.',
        validators=[EmailValidator(message='Ingrese un correo electrónico válido.')]
    )
    tipo = models.CharField(
        max_length=10,
        choices=TIPO_OPCIONES,
        default='Regular',
        verbose_name='Tipo de voluntario',
        help_text='Seleccione el tipo de voluntario.'
    )
    area = models.ForeignKey(
        Area,
        on_delete=models.SET_NULL,
        verbose_name='Área asignada',
        help_text='Seleccione el área asignada al voluntario.',
        blank=True,
        null=True
    )
    qr_code = models.ImageField(
        upload_to='qr_codes/',
        blank=True,
        verbose_name='Código QR',
        help_text='Código QR generado automáticamente.'
    )

    def __str__(self):
        return f"{self.nombre} ({self.tipo})"

    def save(self, *args, **kwargs):
        if not self.qr_code:  # Generar QR solo si no existe
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(self.identificacion)
            qr.make(fit=True)

            img = qr.make_image(fill='black', back_color='white')
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            file_name = f'qr_{self.identificacion}.png'
            self.qr_code.save(file_name, File(buffer), save=False)

        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Voluntario'
        verbose_name_plural = 'Voluntarios'
        ordering = ['nombre']


class Asignacion(models.Model):
    """
    Modelo para representar la asignación y asistencia de un voluntario.
    """
    voluntario = models.ForeignKey(
        Voluntario,
        on_delete=models.CASCADE,
        verbose_name='Voluntario',
        help_text='Seleccione el voluntario.'
    )
    area = models.ForeignKey(
        Area,
        on_delete=models.CASCADE,
        verbose_name='Área asignada',
        help_text='Área donde está asignado el voluntario.'
    )
    fecha = models.DateField(
        default=now,
        verbose_name='Fecha de asignación',
        help_text='Fecha en que se realizó la asignación.'
    )
    entrada = models.TimeField(
        verbose_name='Hora de entrada',
        help_text='Hora en que el voluntario registró su entrada.',
        blank=True,
        null=True
    )
    salida = models.TimeField(
        verbose_name='Hora de salida',
        help_text='Hora en que el voluntario registró su salida.',
        blank=True,
        null=True
    )

    def __str__(self):
        return f"{self.voluntario.nombre} - {self.area.nombre} ({self.fecha})"

    def registrar_salida(self):
        """
        Registra la hora de salida y libera el lugar en el área.
        """
        if not self.salida:
            self.salida = now().time()
            self.save()

    class Meta:
        verbose_name = 'Asignación'
        verbose_name_plural = 'Asignaciones'
        ordering = ['-fecha', 'entrada']
        constraints = [
            models.UniqueConstraint(
                fields=['voluntario', 'fecha'],
                name='unique_asignacion_voluntario_fecha'
            )
        ]
