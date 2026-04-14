# Generated migration for JDS Cloud Upload feature

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tv', '0006_directorroomcamera_is_active'),
    ]

    operations = [
        migrations.AddField(
            model_name='video',
            name='uploaded_file_id',
            field=models.CharField(blank=True, help_text='JDS Cloud File ID', max_length=255),
        ),
        migrations.AddField(
            model_name='video',
            name='uploaded_file_url',
            field=models.URLField(blank=True, help_text='JDS Cloud View URL', max_length=1000),
        ),
        migrations.AddField(
            model_name='video',
            name='uploaded_file_download_url',
            field=models.URLField(blank=True, help_text='JDS Cloud Download URL', max_length=1000),
        ),
        migrations.AddField(
            model_name='video',
            name='uploaded_file_name',
            field=models.CharField(blank=True, help_text='Original Dateiname', max_length=500),
        ),
        migrations.AddField(
            model_name='video',
            name='uploaded_file_size',
            field=models.BigIntegerField(default=0, help_text='Dateigröße in Bytes'),
        ),
        migrations.AddField(
            model_name='video',
            name='uploaded_file_type',
            field=models.CharField(blank=True, help_text='MIME Type', max_length=100),
        ),
        migrations.AlterField(
            model_name='video',
            name='source_type',
            field=models.CharField(
                choices=[
                    ('youtube', 'YouTube'),
                    ('gdrive', 'Google Drive'),
                    ('dropbox', 'Dropbox'),
                    ('direct', 'Direkt-URL'),
                    ('twitch', 'Twitch VOD'),
                    ('upload', 'Hochgeladene Datei'),
                ],
                default='youtube',
                max_length=20
            ),
        ),
        migrations.AlterField(
            model_name='video',
            name='source_url',
            field=models.URLField(blank=True, max_length=500),
        ),
    ]
