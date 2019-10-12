# Generated by Django 2.2.6 on 2019-10-12 02:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('API', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='inflection',
            name='lc',
            field=models.CharField(choices=[('NA', 'NA'), ('NAD', 'NAD'), ('NI', 'NI'), ('NID', 'NID'), ('VAI', 'VAI'), ('VII', 'VII'), ('VTA', 'VTA'), ('VTI', 'VTI'), ('IPC', 'IPC'), ('PRON', 'PRON'), ('', '')], help_text='lexical category parsed from xml', max_length=4),
        ),
        migrations.AlterField(
            model_name='inflection',
            name='pos',
            field=models.CharField(choices=[('IPV', 'IPV'), ('PRON', 'PRON'), ('N', 'N'), ('IPC', 'IPC'), ('V', 'V'), ('', '')], help_text='part of speech parsed from xml', max_length=4),
        ),
    ]
