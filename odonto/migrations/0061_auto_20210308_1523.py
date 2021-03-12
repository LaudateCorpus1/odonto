# Generated by Django 2.0.13 on 2021-03-08 15:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('odonto', '0060_auto_20210308_1343'),
    ]

    operations = [
        migrations.AlterField(
            model_name='covidtriage',
            name='date_of_contact',
            field=models.DateField(blank=True, null=True, verbose_name='Date of contact'),
        ),
        migrations.AlterField(
            model_name='covidtriage',
            name='time_of_contact',
            field=models.TimeField(blank=True, null=True, verbose_name='Time the call ended'),
        ),
    ]