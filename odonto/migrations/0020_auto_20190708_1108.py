# Generated by Django 2.0.13 on 2019-07-08 11:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('odonto', '0019_auto_20190625_1317'),
    ]

    operations = [
        migrations.AddField(
            model_name='performernumber',
            name='dpb_pin',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='performernumber',
            name='number',
            field=models.TextField(blank=True, default=''),
        ),
    ]