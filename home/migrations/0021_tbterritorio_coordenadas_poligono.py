

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0020_remove_obsolete_marker_and_region_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='tbterritorio',
            name='coordenadas_poligono',
            field=models.JSONField(blank=True, db_column='CoordenadasPoligono', help_text='Coordenadas GeoJSON para renderizar a área no mapa.', null=True),
        ),
    ]
