# Generated by Django 3.2.4 on 2021-07-14 11:26
from django.contrib.postgres.operations import UnaccentExtension
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("nickelodeon", "0004_auto_20200407_1656"),
    ]

    operations = [UnaccentExtension()]
