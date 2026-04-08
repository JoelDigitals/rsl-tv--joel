# Generated migration for DirectorRoomCamera.is_active field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tv', '0005_streamoverlay_cutoutgraphic_pausescreen_streampreset'),
    ]

    operations = [
        migrations.AddField(
            model_name='directorroomcamera',
            name='is_active',
            field=models.BooleanField(default=False, help_text='Ist diese Kamera aktuell aktiv?'),
        ),
    ]
