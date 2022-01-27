# Generated by Django 3.2.11 on 2022-01-17 18:05

from django.db import migrations, models
import nickelodeon.utils


class Migration(migrations.Migration):

    dependencies = [
        ('nickelodeon', '0006_usersettings'),
    ]

    operations = [
        migrations.AlterField(
            model_name='usersettings',
            name='storage_prefix',
            field=models.CharField(default=nickelodeon.utils.random_key, max_length=32, unique=True),
        ),
    ]